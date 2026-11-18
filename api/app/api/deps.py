"""FastAPI dependencies: the only place routes get their collaborators from."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import (
    ForbiddenError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from app.core.security import AuthenticatedUser, TokenVerifier
from app.services.hello_service import HelloService
from app.services.resource_service import ResourceProbes, ResourceService

# auto_error=False: a missing header becomes our own 401 JSON error.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_hello_service() -> HelloService:
    return HelloService()


def get_resource_service(request: Request) -> ResourceService:
    probes: ResourceProbes = request.app.state.resource_probes
    return ResourceService(probes)


def get_token_verifier(request: Request) -> TokenVerifier:
    verifier: TokenVerifier | None = request.app.state.token_verifier
    if verifier is None:
        raise ServiceUnavailableError(
            "Authentication is not configured (no Hub public key or app uuid)."
        )
    return verifier


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> AuthenticatedUser:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token.")
    return verifier.verify(credentials.credentials)


def require_admin(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if not user.is_admin:
        raise ForbiddenError("Administrator access required.")
    return user


HelloServiceDep = Annotated[HelloService, Depends(get_hello_service)]
ResourceServiceDep = Annotated[ResourceService, Depends(get_resource_service)]
CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]
