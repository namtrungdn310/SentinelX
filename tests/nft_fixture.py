"""Small nft JSON protocol fixture; Linux acceptance separately checks the real kernel."""

import json
import re
import time
from typing import Any


def schema(table: str = "sentinelx", hook: str = "input") -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = [{"table": {"family": "inet", "name": table}}]
    for name, kind in (("blocked_v4", "ipv4_addr"), ("blocked_v6", "ipv6_addr")):
        objects.append(
            {
                "set": {
                    "family": "inet",
                    "table": table,
                    "name": name,
                    "type": kind,
                    "flags": ["timeout"],
                    "size": 10000,
                }
            }
        )
    objects.append(
        {
            "chain": {
                "family": "inet",
                "table": table,
                "name": "guard",
                "type": "filter",
                "hook": hook,
                "prio": -100,
                "policy": "accept",
            }
        }
    )
    for protocol, name in (("ip", "blocked_v4"), ("ip6", "blocked_v6")):
        objects.append(
            {
                "rule": {
                    "table": table,
                    "chain": "guard",
                    "expr": [
                        {
                            "match": {
                                "op": "==",
                                "left": {"payload": {"protocol": protocol, "field": "saddr"}},
                                "right": "@" + name,
                            }
                        },
                        {"drop": None},
                    ],
                }
            }
        )
    return objects


class NftKernelFixture:
    def __init__(self) -> None:
        self.objects: list[dict[str, Any]] | None = schema()
        self.elements: dict[str, tuple[str, float]] = {}
        self.calls: list[tuple[list[str], str | None]] = []
        self.failure: str | None = None

    async def __call__(self, argv: list[str], stdin: str | None) -> tuple[int, str, str]:
        self.calls.append((argv, stdin))
        if self.failure:
            return 1, "", self.failure
        if "list" in argv and "set" in argv:
            elements = [
                {
                    "elem": {
                        "val": target,
                        "comment": owner,
                        "expires": int((expiry - time.time()) * 1000),
                    }
                }
                for target, (owner, expiry) in self.elements.items()
                if expiry > time.time()
            ]
            return 0, json.dumps({"nftables": [{"set": {"elem": elements}}]}), ""
        if "list" in argv:
            if self.objects is None:
                return 1, "", "No such file or directory"
            return 0, json.dumps({"nftables": self.objects}), ""
        if "get" in argv:
            target = argv[-1].strip("{} ")
            item = self.elements.get(target)
            if item is None or item[1] <= time.time():
                self.elements.pop(target, None)
                return 1, "", "No such file or directory"
            value = {
                "elem": {
                    "val": target,
                    "comment": item[0],
                    "expires": int((item[1] - time.time()) * 1000),
                }
            }
            return 0, json.dumps({"nftables": [{"set": {"elem": [value]}}]}), ""
        if stdin and stdin.startswith("table inet"):
            self.objects = schema()
            return 0, "", ""
        for line in (stdin or "").splitlines():
            if line.startswith("delete element"):
                self.elements.pop(line.split("{")[1].split("}")[0].strip(), None)
            elif line.startswith("add element"):
                match = re.search(r'\{ (\S+) timeout (\d+)s comment "([^"]+)" \}', line)
                assert match, line
                self.elements[match[1]] = (match[3], time.time() + int(match[2]))
            else:
                raise AssertionError(f"Unexpected nft protocol command: {line}")
        return 0, "", ""
