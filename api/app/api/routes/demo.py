from fastapi import APIRouter, Depends

from app.api.deps import (
    CurrentUserDep,
    DemoAdminServiceDep,
    DemoServiceDep,
    require_admin,
)
from app.schemas.demo import DemoState, DemoVisit
from app.schemas.demo_admin import DemoOverview

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


# The calls of the backoffice plugin (plugin/): the admin guard is declared once on the
# router, like the one of routes/admin.py.
admin_router = APIRouter(
    prefix="/admin/demo",
    tags=["demo", "admin"],
    dependencies=[Depends(require_admin)],
)


@admin_router.get(
    "/overview", summary="What the database, the cache and the bucket hold"
)
def read_overview(service: DemoAdminServiceDep) -> DemoOverview:
    return service.overview()


@admin_router.post(
    "/reset-cache", summary="Reset the visit counter of the cache, return the overview"
)
def reset_cache(service: DemoAdminServiceDep) -> DemoOverview:
    return service.reset_cache_visits()


router.include_router(admin_router)
