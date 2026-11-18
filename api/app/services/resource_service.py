import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import Config
from app.schemas.resources import ResourcesStatus, ResourceState
from app.services import resource_probes

logger = logging.getLogger(__name__)

Probe = Callable[[], None]


@dataclass(frozen=True)
class ResourceProbes:
    """The checks to run, ``None`` when the resource is not configured."""

    database: Probe | None
    cache: Probe | None
    storage: Probe | None

    @classmethod
    def from_config(cls, config: Config) -> ResourceProbes:
        database, cache, storage = config.database, config.cache, config.storage
        return cls(
            database=(lambda: resource_probes.probe_database(database))
            if database.url.get_secret_value()
            else None,
            cache=(lambda: resource_probes.probe_cache(cache))
            if cache.url.get_secret_value()
            else None,
            storage=(lambda: resource_probes.probe_storage(storage))
            if storage.endpoint and storage.bucket
            else None,
        )


class ResourceService:
    """Tells whether the mini-app's DEV resources answer. Knows nothing about HTTP."""

    def __init__(self, probes: ResourceProbes) -> None:
        self._probes = probes

    def status(self) -> ResourcesStatus:
        return ResourcesStatus(
            database=_run("database", self._probes.database),
            cache=_run("cache", self._probes.cache),
            storage=_run("storage", self._probes.storage),
        )


def _run(name: str, probe: Probe | None) -> ResourceState:
    if probe is None:
        return "not_configured"
    try:
        probe()
    except Exception:
        # The cause may name a host or a user: logs only, never the response.
        logger.warning("resource %s unreachable", name, exc_info=True)
        return "unreachable"
    return "ok"
