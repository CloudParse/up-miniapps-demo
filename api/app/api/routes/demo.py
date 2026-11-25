from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.api.deps import (
    CurrentUserDep,
    DemoAdminServiceDep,
    DemoServiceDep,
    RealtimeHubDep,
    require_admin,
)
from app.schemas.demo import DemoCounters, DemoState, DemoVisit
from app.schemas.demo_admin import DemoNote, DemoNoteCreate, DemoOverview
from app.services.realtime_service import counter_reset, visit_recorded

# Mounted only outside production (app/main.py): in production these routes answer 404.
router = APIRouter(tags=["demo"])


@router.get("/demo", summary="Is the demo of the DEV resources served here?")
def read_demo() -> DemoState:
    return DemoState(enabled=True)


@router.post(
    "/demo/visit",
    summary="Write one row, one counter and one object, and read them back",
)
async def record_visit(
    user: CurrentUserDep, service: DemoServiceDep, hub: RealtimeHubDep
) -> DemoVisit:
    # The service blocks (database, cache, bucket): a thread. The push is async.
    visit = await run_in_threadpool(service.record_visit, str(user.user_uuid))
    # Every open mini-app and plugin updates its counters (docs/realtime.md).
    await hub.publish(visit_recorded(visit.database_visits, visit.cache_visits))
    return visit


@router.get("/demo/counters", summary="Read the two visit counters")
async def read_counters(
    _: CurrentUserDep, service: DemoAdminServiceDep
) -> DemoCounters:
    database, cache = await run_in_threadpool(service.counters)
    return DemoCounters(database_visits=database, cache_visits=cache)


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
async def reset_cache(
    service: DemoAdminServiceDep, hub: RealtimeHubDep
) -> DemoOverview:
    overview = await run_in_threadpool(service.reset_cache_visits)
    await hub.publish(counter_reset())
    return overview


@admin_router.get("/notes", summary="The newest notes the admins wrote")
def list_notes(service: DemoAdminServiceDep) -> list[DemoNote]:
    return service.list_notes()


@admin_router.post(
    "/notes", status_code=201, summary="Write one note in the database of the mini-app"
)
def add_note(body: DemoNoteCreate, service: DemoAdminServiceDep) -> DemoNote:
    return service.add_note(body.text)


router.include_router(admin_router)
