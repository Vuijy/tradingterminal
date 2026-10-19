from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from app.api.deps import ProviderDep
from app.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(provider: ProviderDep) -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "env": settings.app_env,
        "provider": provider.name,
        "time": datetime.now(UTC).isoformat(),
    }
