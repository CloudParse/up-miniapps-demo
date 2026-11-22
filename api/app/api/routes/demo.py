from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DemoServiceDep
from app.schemas.demo import DemoVisit

router = APIRouter(tags=["demo"])


@router.post(
    "/demo/visit",
    summary="Write one row, one counter and one object, and read them back",
)
def record_visit(user: CurrentUserDep, service: DemoServiceDep) -> DemoVisit:
    return service.record_visit(str(user.user_uuid))
