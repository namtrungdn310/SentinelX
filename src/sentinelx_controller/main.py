"""Main entry point for SentinelX Controller application."""

import uvicorn

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings


def run() -> None:
    """Load settings and run the Uvicorn server."""
    settings = ControllerSettings.load()
    app = create_app(settings=settings)

    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.port,
        log_config=None,  # We manage logging via structured logging setup
    )


if __name__ == "__main__":
    run()
