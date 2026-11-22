from app.schemas.base import CamelModel


class DemoVisit(CamelModel):
    """What one demo visit wrote and read back.

    ``None``: that resource is not configured here.
    """

    database_visits: int | None
    cache_visits: int | None
    storage_object: str | None
