"""Development entry point: `python -m app` or `uv run python -m app`.

Both read ``api/.env`` themselves, wherever they are started from.
"""

import logging
from pathlib import Path

import uvicorn

from app.core.config import get_config
from app.core.dotenv import load_dotenv

logger = logging.getLogger(__name__)
# api/.env, found from this file and not from the working directory. Absent in the
# production image: then nothing is loaded.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    # Before get_config(): the config reads the environment. The reload worker
    # inherits it.
    loaded = load_dotenv(ENV_FILE)
    if loaded:
        logger.info("%d variable(s) loaded from %s", len(loaded), ENV_FILE.name)
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
