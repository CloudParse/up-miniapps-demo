from pydantic import Field

from app.schemas.base import CamelModel


class BroadcastRequest(CamelModel):
    text: str = Field(min_length=1, max_length=200)


class BroadcastResult(CamelModel):
    """How many open sockets received the message."""

    delivered: int
