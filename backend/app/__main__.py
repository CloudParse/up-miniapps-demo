"""Development entry point: `uv run --env-file .env python -m app`."""

import logging

import uvicorn

from app.core.config import get_config


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = get_config()
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=config.server.host,
        port=config.server.port,
        reload=config.environment == "development",
    )


if __name__ == "__main__":
    main()
