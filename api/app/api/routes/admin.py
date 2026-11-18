from fastapi import APIRouter, Depends

from app.api.deps import HelloServiceDep, require_admin
from app.schemas.hello import Greeting

# Every route of this router needs the admin scope: the guard is declared once
# on the router, so a new admin route cannot forget it.
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/hello", summary="Say hello to an administrator")
def say_hello_to_admin(service: HelloServiceDep) -> Greeting:
    return service.greet("administrator")
