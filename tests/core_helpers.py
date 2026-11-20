"""Controller protocol harness. APPLIED receipts here are fixtures, not kernel evidence."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings, DatabaseSettings
from sentinelx_controller.infrastructure.database.base import Base
from sentinelx_controller.infrastructure.database.session import get_db_session


@dataclass
class CoreHarness:
    client: AsyncClient
    sessions: async_sessionmaker[AsyncSession]
    project: str
    node: str
    agent: str
    ack_times: dict[str, str] = field(default_factory=dict)

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self.client.post("/api/v1" + path, json=payload)
        assert response.is_success, response.text
        return dict(response.json())

    async def heartbeat(
        self, *, version: int = 2, supported_actions: list[str] | None = None
    ) -> list[dict[str, Any]]:
        actions = supported_actions or [
            "BLOCK_IP_NFTABLES",
            "UNBLOCK_IP_NFTABLES",
            "ALERT_ONLY",
            "RESTART_SERVICE",
            "CLEAR_OS_CACHE",
        ]
        response = await self.post(
            "/nodes/heartbeat",
            {
                "node_id": self.node,
                "agent_id": self.agent,
                "sequence": 1,
                "sent_at": datetime.now(UTC).isoformat(),
                "command_protocol_version": version,
                "executor_mode": "nftables",
                "supported_actions": actions,
            },
        )
        return list(response["commands"])

    async def block(self, duration: int = 60, **fields: Any) -> dict[str, Any]:
        return await self.post(
            "/defense/actions",
            {
                "node_id": self.node,
                "action_type": "BLOCK_IP_NFTABLES",
                "target_ip": "198.51.100.77",
                "command_payload": {"duration_seconds": duration},
                **fields,
            },
        )

    async def ack(
        self,
        command: dict[str, Any],
        state: str = "APPLIED",
        **overrides: Any,
    ) -> Response:
        return await self.client.post(
            f"/api/v1/defense/actions/{command['id']}/ack",
            json={
                "action_id": command["id"],
                "node_id": self.node,
                "agent_id": self.agent,
                "delivery_token": command["delivery_token"],
                "status": state,
                "executed_at": self.ack_times.setdefault(
                    command["id"], datetime.now(UTC).isoformat()
                ),
                "execution_metadata": {"executor": "nftables"},
                **overrides,
            },
        )


@asynccontextmanager
async def core_harness(
    database_url: str = "sqlite+aiosqlite:///:memory:",
) -> AsyncIterator[CoreHarness]:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app(
        ControllerSettings(
            environment="testing",
            database=DatabaseSettings(url=database_url),
        )
    )

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = session_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://audit",
        ) as client:
            project = (await client.post("/api/v1/projects", json={"name": uuid4().hex})).json()[
                "project_id"
            ]
            node = (
                await client.post(
                    "/api/v1/nodes",
                    json={
                        "project_id": project,
                        "hostname": "guard",
                        "ip_address": "192.0.2.11",
                    },
                )
            ).json()["node_id"]
            token = (await client.post(f"/api/v1/nodes/{node}/enrollment-tokens", json={})).json()[
                "enrollment_token"
            ]
            agent = (
                await client.post(
                    "/api/v1/nodes/enroll",
                    json={
                        "node_id": node,
                        "enrollment_token": token,
                        "hostname": "guard",
                        "agent_version": "qa",
                    },
                )
            ).json()["agent_id"]
            yield CoreHarness(client, sessions, project, node, agent)
    finally:
        await engine.dispose()
