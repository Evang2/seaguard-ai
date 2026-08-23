from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from seaguard.api.routes.anomalies import router as anomalies_router
from seaguard.api.routes.collisions import router as collision_router
from seaguard.api.routes.health import router as health_router
from seaguard.api.routes.positions import router as positions_router
from seaguard.api.routes.risk_routes import router as risk_router
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


allowed_origins = {
    settings.frontend_origin,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    health_router,
    prefix="/api/v1",
)

app.include_router(vessels_router)
app.include_router(positions_router)
app.include_router(anomalies_router)
app.include_router(risk_router)

app.include_router(
    collision_router,
    prefix="/api/v1",
)


@app.get(
    "/",
    tags=["Root"],
)
def root() -> dict[str, str]:
    """Return basic information about the API."""

    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "documentation": "/docs",
    }
