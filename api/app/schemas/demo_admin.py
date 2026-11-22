from app.schemas.base import CamelModel


class DemoOverview(CamelModel):
    """What the three DEV resources hold, as the backoffice plugin shows it.

    ``None``: that resource is not configured here.
    """

    database_visits: int | None
    cache_visits: int | None
    storage_objects: int | None
