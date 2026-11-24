"""What the backoffice plugin of the demo reads and changes.

The plugin never gets a database, cache or bucket credential: it calls the admin routes
of this API, and this service uses the resources with the API's own settings. Like
``demo_service``, it is an example to delete before you ship, and every resource is
optional.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import psycopg
from psycopg import errors as pg_errors

from app.core.config import Config
from app.core.errors import ServiceUnavailableError
from app.schemas.demo_admin import DemoNote, DemoOverview
from app.services.demo_service import (
    cache_client,
    ensure_schema,
    storage_client,
    visits_cache_key,
)
from app.services.resource_probes import TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# The objects `demo_service` writes: one per visitor, under this prefix.
STORAGE_PREFIX = "demo/"
# A demo counts, it does not scan a whole bucket: stop at this many objects.
MAX_COUNTED_OBJECTS = 1000

Count = Callable[[], int]
Reset = Callable[[], None]
ListNotes = Callable[[], list[DemoNote]]
AddNote = Callable[[str], DemoNote]

# The plugin lists the newest notes only: a demo, not a paginated list.
MAX_LISTED_NOTES = 50
_NO_DATABASE = "The database of the mini-app is not configured."
_DATABASE_DOWN = "The database of the mini-app does not answer."


@dataclass(frozen=True)
class DemoAdminActions:
    database_visits: Count | None
    cache_visits: Count | None
    storage_objects: Count | None
    reset_cache_visits: Reset | None
    list_notes: ListNotes | None = None
    add_note: AddNote | None = None

    @classmethod
    def from_config(cls, config: Config) -> DemoAdminActions:
        db_url = config.database.url.get_secret_value()
        cache_url = config.cache.url.get_secret_value()
        prefix = config.cache.key_prefix
        has_storage = bool(config.storage.endpoint and config.storage.bucket)
        return cls(
            database_visits=(lambda: _count_visits(db_url)) if db_url else None,
            cache_visits=(lambda: _read_cache_visits(cache_url, prefix))
            if cache_url
            else None,
            storage_objects=(lambda: _count_objects(config)) if has_storage else None,
            reset_cache_visits=(lambda: _reset_cache_visits(cache_url, prefix))
            if cache_url
            else None,
            list_notes=(lambda: _list_notes(db_url)) if db_url else None,
            add_note=(lambda text: _add_note(db_url, text)) if db_url else None,
        )


class DemoAdminService:
    def __init__(self, actions: DemoAdminActions) -> None:
        self._actions = actions

    def overview(self) -> DemoOverview:
        a = self._actions
        return DemoOverview(
            database_visits=_read("database", a.database_visits),
            cache_visits=_read("cache", a.cache_visits),
            storage_objects=_read("bucket", a.storage_objects),
        )

    def reset_cache_visits(self) -> DemoOverview:
        if self._actions.reset_cache_visits:
            self._actions.reset_cache_visits()
        return self.overview()

    def list_notes(self) -> list[DemoNote]:
        if self._actions.list_notes is None:
            raise ServiceUnavailableError(_NO_DATABASE)
        try:
            return self._actions.list_notes()
        except psycopg.OperationalError as error:
            logger.warning("demo notes: database unreachable", exc_info=True)
            raise ServiceUnavailableError(_DATABASE_DOWN) from error

    def add_note(self, text: str) -> DemoNote:
        if self._actions.add_note is None:
            raise ServiceUnavailableError(_NO_DATABASE)
        try:
            return self._actions.add_note(text)
        except psycopg.OperationalError as error:
            logger.warning("demo notes: database unreachable", exc_info=True)
            raise ServiceUnavailableError(_DATABASE_DOWN) from error


def _read(resource: str, count: Count | None) -> int | None:
    """One failing resource gives None (like "not configured"), not a 500 for all."""
    if count is None:
        return None
    try:
        return count()
    except Exception:  # noqa: BLE001 - any driver error: the other resources still answer
        logger.warning("demo overview: %s unreachable", resource, exc_info=True)
        return None


def _count_visits(url: str) -> int:
    with psycopg.connect(url, connect_timeout=TIMEOUT_SECONDS) as connection:
        row = connection.execute("SELECT count(*) FROM demo_visits").fetchone()
        return int(row[0]) if row else 0


def _read_cache_visits(url: str, key_prefix: str) -> int:
    client = cache_client(url)
    try:
        value = client.get(visits_cache_key(key_prefix))
        return int(value) if value is not None else 0
    finally:
        client.close()


def _reset_cache_visits(url: str, key_prefix: str) -> None:
    client = cache_client(url)
    try:
        client.delete(visits_cache_key(key_prefix))
    finally:
        client.close()


def _count_objects(config: Config) -> int:
    client = storage_client(config)
    response = client.list_objects_v2(
        Bucket=config.storage.bucket,
        Prefix=STORAGE_PREFIX,
        MaxKeys=MAX_COUNTED_OBJECTS,
    )
    return int(response.get("KeyCount", 0))


def _list_notes(url: str) -> list[DemoNote]:
    try:
        rows = _select_notes(url)
    except pg_errors.UndefinedTable:
        # The table was not there at startup (database not ready yet): once, here.
        ensure_schema(url)
        rows = _select_notes(url)
    return [DemoNote(id=row[0], text=row[1], created_at=row[2]) for row in rows]


def _select_notes(url: str) -> list[tuple[int, str, datetime]]:
    with psycopg.connect(url, connect_timeout=TIMEOUT_SECONDS) as connection:
        return connection.execute(
            "SELECT id, text, created_at FROM demo_notes ORDER BY id DESC LIMIT %s",
            (MAX_LISTED_NOTES,),
        ).fetchall()


def _add_note(url: str, text: str) -> DemoNote:
    try:
        row = _insert_note(url, text)
    except pg_errors.UndefinedTable:
        ensure_schema(url)
        row = _insert_note(url, text)
    if row is None:
        raise ServiceUnavailableError("The note was not saved.")
    return DemoNote(id=row[0], text=row[1], created_at=row[2])


def _insert_note(url: str, text: str) -> tuple[int, str, datetime] | None:
    with psycopg.connect(url, connect_timeout=TIMEOUT_SECONDS) as connection:
        return connection.execute(
            "INSERT INTO demo_notes (text) VALUES (%s) RETURNING id, text, created_at",
            (text,),
        ).fetchone()
