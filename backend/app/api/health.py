from fastapi import APIRouter

from app.schemas import HealthResponse
from app.scheduler import get_scheduler_status
from app.connectors.base import get_registered_connectors
from app.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    running, heartbeat = get_scheduler_status()
    return HealthResponse(
        status="ok",
        scheduler_running=running,
        last_scheduler_heartbeat=heartbeat,
    )


@router.get("/connectors")
def list_connectors():
    """List all registered connector types and their credential status."""
    registry = get_registered_connectors()
    result = []
    for ctype, cls in sorted(registry.items()):
        configured = all(getattr(settings, env_key, None) for env_key in cls.required_env)
        result.append({
            "connector_type": ctype,
            "required_env": cls.required_env,
            "configured": configured,
            "has_mock_data": bool(cls.mock_data),
        })
    return result
