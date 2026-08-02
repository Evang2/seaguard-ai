from fastapi import FastAPI


app = FastAPI(
    title="SeaGuard AI API",
    description=(
        "AI-assisted maritime vessel monitoring, "
        "anomaly detection, and collision-risk API."
    ),
    version="0.1.0",
)


@app.get("/")
def root() -> dict[str, str]:
    """Return basic information about the API."""

    return {
        "name": "SeaGuard AI API",
        "version": "0.1.0",
        "documentation": "/docs",
    }


@app.get("/api/v1/health")
def health_check() -> dict[str, str]:
    """Confirm that the backend process is running."""

    return {
        "status": "ok",
        "service": "seaguard-api",
    }
