from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DemoServiceDep
from app.schemas.demo import DemoState, DemoVisit

# Mounted only outside production (app/main.py): in production these routes answer 404.
router = APIRouter(tags=["demo"])


@router.get("/demo", summary="Is the demo of the DEV resources served here?")
def read_demo() -> DemoState:
    return DemoState(enabled=True)


@router.post(
    "/demo/visit",
    summary="Write one row, one counter and one object, and read them back",
)
def record_visit(user: CurrentUserDep, service: DemoServiceDep) -> DemoVisit:
    return service.record_visit(str(user.user_uuid))
