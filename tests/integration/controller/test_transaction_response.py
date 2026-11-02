"""A successful REST response must not precede its database commit."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import Message, Receive, Scope, Send

from sentinelx_controller.app import create_app
from sentinelx_controller.infrastructure.database.session import get_db_session
from sentinelx_controller.modules.projects.service import ProjectService


@pytest.mark.asyncio
@pytest.mark.parametrize("commit_fails", [False, True])
async def test_commit_finishes_before_success_response(
    monkeypatch: pytest.MonkeyPatch, commit_fails: bool
) -> None:
    app = create_app()
    committed = False

    async def session() -> AsyncGenerator[AsyncSession, None]:
        nonlocal committed
        yield AsyncMock(spec=AsyncSession)
        if commit_fails:
            raise RuntimeError("Commit failed")
        committed = True

    app.dependency_overrides[get_db_session] = session
    monkeypatch.setattr(ProjectService, "list_projects", AsyncMock(return_value=[]))

    async def checked_app(scope: Scope, receive: Receive, send: Send) -> None:
        async def checked_send(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] < 400:
                assert committed, "Success response was sent before the transaction committed"
            await send(message)

        await app(scope, receive, checked_send)

    async with AsyncClient(
        transport=ASGITransport(app=checked_app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/projects")
    assert response.status_code == (500 if commit_fails else 200)
    assert committed is not commit_fails
