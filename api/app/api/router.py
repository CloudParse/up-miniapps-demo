from fastapi import APIRouter

from app.api.routes import admin, hello, me, realtime, resources

# Everything mounted here is served under /api/v1.
api_router = APIRouter()
api_router.include_router(hello.router)
api_router.include_router(me.router)
api_router.include_router(admin.router)
api_router.include_router(resources.router)
api_router.include_router(realtime.router)
