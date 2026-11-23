from uuid import UUID

from app.schemas.base import CamelModel


class CurrentUser(CamelModel):
    user_uuid: UUID
    is_admin: bool
