from fastapi import APIRouter

from app.api.deps import CurrentUserDep, ResourceServiceDep
from app.schemas.resources import ResourcesStatus

router = APIRouter(tags=["resources"])


@router.get("/resources", summary="Check the mini-app's DEV resources")
def read_resources(_: CurrentUserDep, service: ResourceServiceDep) -> ResourcesStatus:
    return service.status()
