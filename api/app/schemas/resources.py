from typing import Literal

from app.schemas.base import CamelModel

ResourceState = Literal["ok", "not_configured", "unreachable"]


class ResourcesStatus(CamelModel):
    """Whether each DEV resource of the mini-app answers. Never a credential."""

    database: ResourceState
    cache: ResourceState
    storage: ResourceState
