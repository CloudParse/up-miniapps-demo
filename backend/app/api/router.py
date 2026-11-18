from fastapi import APIRouter

from app.api.routes import admin, hello, me

# Everything mounted here is served under /api/v1.
api_router = APIRouter()
api_router.include_router(hello.router)
api_router.include_router(me.router)
api_router.include_router(admin.router)
