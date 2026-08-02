from fastapi import FastAPI

from seaguard.api.routes.health import router as health_router
from seaguard.core.config import get_settings

settings = get_settings()


app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-assisted maritime vessel monitoring, "
        "anomaly detection, and collision-risk API."
    ),
    version="0.1.0",
    debug=settings.app_debug,
)


app.include_router(
    health_router,
    prefix="/api/v1",
)


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    """Return basic information about the API."""

    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "documentation": "/docs",
    }