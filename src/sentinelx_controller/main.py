"""Entry point to start SentinelX Controller."""

import uvicorn

from sentinelx_controller.app import create_app
from sentinelx_controller.config import ControllerSettings


def run() -> None:
    """Load config and start the server with Uvicorn."""
    settings = ControllerSettings.load()
    app = create_app(settings=settings)

    uvicorn.run(
        app,
        host=settings.server.host,
        port=settings.server.port,
        log_config=None,  # Use custom logger instead of Uvicorn default logger
    )


if __name__ == "__main__":
    run()
