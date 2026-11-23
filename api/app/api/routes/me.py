from fastapi import APIRouter

from app.api.deps import CurrentUserDep
from app.schemas.me import CurrentUser

router = APIRouter(tags=["me"])


@router.get("/me", summary="Identify the calling user")
def read_current_user(user: CurrentUserDep) -> CurrentUser:
    return CurrentUser(user_uuid=user.user_uuid, is_admin=user.is_admin)
