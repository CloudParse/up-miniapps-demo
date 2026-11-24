from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from app.schemas.base import CamelModel


class DemoOverview(CamelModel):
    """What the three DEV resources hold, as the backoffice plugin shows it.

    ``None``: that resource is not configured here.
    """

    database_visits: int | None
    cache_visits: int | None
    storage_objects: int | None


NoteText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class DemoNoteCreate(CamelModel):
    """What an admin types in the plugin's "New note" modal."""

    text: NoteText


class DemoNote(CamelModel):
    """One row of the ``demo_notes`` table, written by an admin from the plugin."""

    id: int
    text: str
    created_at: datetime
