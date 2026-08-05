from fastapi import APIRouter

from app.api.routes import dashboard, data, exams, imports, profile

api_router = APIRouter()
api_router.include_router(dashboard.router)
api_router.include_router(exams.router)
api_router.include_router(imports.router)
api_router.include_router(profile.router)
api_router.include_router(data.router)
