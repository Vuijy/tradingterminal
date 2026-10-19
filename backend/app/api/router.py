from fastapi import APIRouter

from app.api.routes import companies, health, macro, quotes, relationships

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(companies.router)
api_router.include_router(relationships.router)
api_router.include_router(quotes.router)
api_router.include_router(macro.router)
