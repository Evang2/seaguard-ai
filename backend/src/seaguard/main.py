from fastapi import FastAPI

from seaguard.api.routes.anomalies import router as anomalies_router
from seaguard.api.routes.health import router as health_router
from seaguard.api.routes.positions import router as positions_router
from seaguard.api.routes.vessels import router as vessels_router
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


# The health router defines routes such as /health and
# /health/database, so the API version prefix is added here.
app.include_router(
    health_router,
    prefix="/api/v1",
)

# These routers already contain their complete /api/v1 prefixes.
app.include_router(vessels_router)
app.include_router(positions_router)
app.include_router(anomalies_router)


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    """Return basic information about the API."""

    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "documentation": "/docs",
    }
