from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from seaguard.db.session import get_database_session

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


DatabaseSession = Annotated[
    Session,
    Depends(get_database_session),
]


@router.get("")
def application_health() -> dict[str, str]:
    """Confirm that the FastAPI application is running."""

    return {
        "status": "ok",
        "service": "seaguard-api",
    }


@router.get("/database")
def database_health(
    session: DatabaseSession,
) -> dict[str, str]:
    """Confirm that PostgreSQL and PostGIS are available."""

    try:
        database_name = session.execute(
            text("SELECT current_database()")
        ).scalar_one()

        postgis_version = session.execute(
            text("SELECT PostGIS_Version()")
        ).scalar_one()

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is unavailable.",
        ) from error

    return {
        "status": "ok",
        "database": database_name,
        "postgis": postgis_version,
    }