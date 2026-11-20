"""SQLite command journal: bounded execution receipts survive Agent restarts."""

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sentinelx_common.contracts.defense import AgentCommandContract, CommandAckRequest


class CommandJournal:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS commands (
                id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, command TEXT NOT NULL,
                result TEXT, acknowledged INTEGER NOT NULL DEFAULT 0,
                expires REAL NOT NULL, execution_lease REAL NOT NULL
            )""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(commands)")}
            if "ack_attempts" not in columns:
                db.execute(
                    "ALTER TABLE commands ADD COLUMN ack_attempts INTEGER NOT NULL DEFAULT 0"
                )
                db.execute(
                    "ALTER TABLE commands ADD COLUMN next_ack_attempt REAL NOT NULL DEFAULT 0"
                )
        os.chmod(path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    @staticmethod
    def _fingerprint(command: AgentCommandContract) -> str:
        value = command.model_dump(mode="json", exclude={"delivery_token"})
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def reserve(
        self,
        command: AgentCommandContract,
    ) -> tuple[AgentCommandContract, CommandAckRequest | None] | None:
        """Claim execution, or return a durable receipt; never execute a changed ID."""
        now = datetime.now(UTC)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "DELETE FROM commands WHERE acknowledged=1 AND expires < ?",
                ((now - timedelta(days=1)).timestamp(),),
            )
            row = db.execute(
                "SELECT fingerprint,command,result,execution_lease FROM commands WHERE id=?",
                (command.id,),
            ).fetchone()
            if row:
                if row[0] != self._fingerprint(command):
                    raise ValueError("Command ID was reused with a different payload")
                stored = AgentCommandContract.model_validate_json(row[1])
                if row[2]:
                    return stored, CommandAckRequest.model_validate_json(row[2])
                if row[3] > now.timestamp():
                    return None
                db.execute(
                    "UPDATE commands SET execution_lease=? WHERE id=?",
                    (now.timestamp() + 15, command.id),
                )
                return stored, None
            if db.execute("SELECT count(*) FROM commands").fetchone()[0] >= 10000:
                raise RuntimeError(
                    "Command journal capacity reached; operator reconciliation needed"
                )
            parameters = dict(command.command_payload)
            if command.action_type == "BLOCK_IP_NFTABLES":
                duration = parameters.get(
                    "duration_seconds", parameters.get("block_duration_seconds", 1800)
                )
                if (
                    isinstance(duration, int)
                    and not isinstance(duration, bool)
                    and 1 <= duration <= 86400
                ):
                    parameters["effective_until"] = (now + timedelta(seconds=duration)).isoformat()
            stored = command.model_copy(update={"command_payload": parameters})
            db.execute(
                "INSERT INTO commands(id,fingerprint,command,expires,execution_lease) "
                "VALUES(?,?,?,?,?)",
                (
                    command.id,
                    self._fingerprint(command),
                    stored.model_dump_json(),
                    command.expires_at.timestamp(),
                    now.timestamp() + 15,
                ),
            )
            return stored, None

    def complete(self, action_id: str, result: CommandAckRequest) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE commands SET result=? WHERE id=?", (result.model_dump_json(), action_id)
            )

    def acknowledge(self, action_id: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE commands SET acknowledged=1 WHERE id=?", (action_id,))

    def pending(self) -> list[CommandAckRequest]:
        with self._connect() as db:
            rows: list[Any] = db.execute(
                "SELECT result FROM commands WHERE result IS NOT NULL AND acknowledged=0 "
                "AND next_ack_attempt <= ? LIMIT 20",
                (datetime.now(UTC).timestamp(),),
            ).fetchall()
        return [CommandAckRequest.model_validate_json(row[0]) for row in rows]

    def defer_ack(self, action_id: str) -> None:
        with self._connect() as db:
            row = db.execute(
                "SELECT ack_attempts FROM commands WHERE id=?", (action_id,)
            ).fetchone()
            delay = min(60, 2 ** min(row[0] if row else 0, 6))
            db.execute(
                "UPDATE commands SET ack_attempts=ack_attempts+1,next_ack_attempt=? WHERE id=?",
                (datetime.now(UTC).timestamp() + delay, action_id),
            )

    def active_blocks(self) -> list[AgentCommandContract]:
        """Recover live absolute deadlines, excluding any journaled unblock intent."""
        with self._connect() as db:
            rows = db.execute("SELECT command,result FROM commands LIMIT 10000").fetchall()
        blocks: dict[str, AgentCommandContract] = {}
        removed: set[str] = set()
        now = datetime.now(UTC)
        for raw, receipt in rows:
            command = AgentCommandContract.model_validate_json(raw)
            if command.action_type == "UNBLOCK_IP_NFTABLES":
                original = command.command_payload.get("original_defense_action_id")
                if isinstance(original, str):
                    removed.add(original)
            elif command.action_type == "BLOCK_IP_NFTABLES" and receipt:
                result = CommandAckRequest.model_validate_json(receipt)
                deadline = command.command_payload.get("effective_until")
                if (
                    result.status == "APPLIED"
                    and isinstance(deadline, str)
                    and datetime.fromisoformat(deadline) > now
                ):
                    blocks[command.id] = command
        return [command for key, command in blocks.items() if key not in removed]
