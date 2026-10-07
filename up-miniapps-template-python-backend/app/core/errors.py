"""Application errors and the handlers that turn them into JSON responses."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """An expected failure the client may see, with a stable machine code."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


async def _handle_app_error(_request: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, AppError):
        raise error
    return _error_response(error.status_code, error.code, error.message)


async def _handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    # The traceback goes to the logs; the client only gets a generic message.
    logger.error(
        "unhandled error",
        exc_info=error,
        extra={"path": request.url.path, "method": request.method},
    )
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "Something went wrong.",
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
