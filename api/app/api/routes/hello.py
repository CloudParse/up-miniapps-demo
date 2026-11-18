from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import HelloServiceDep
from app.schemas.hello import Greeting

router = APIRouter(tags=["hello"])

NameQuery = Annotated[
    str,
    Query(
        min_length=1,
        max_length=40,
        pattern=r"^[\w .'-]+$",
        description="Who to greet.",
    ),
]


@router.get("/hello", summary="Say hello")
def say_hello(service: HelloServiceDep, name: NameQuery = "World") -> Greeting:
    return service.greet(name)
