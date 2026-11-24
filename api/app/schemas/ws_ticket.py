from pydantic import Field

from app.schemas.base import CamelModel


class WsTicket(CamelModel):
    """A single-use ticket for ``/api/v1/ws?ticket=...``."""

    ticket: str = Field(description="Valid for a few seconds, usable once.")
    expires_in: int = Field(description="Lifetime in seconds.")
