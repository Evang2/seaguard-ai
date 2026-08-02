from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from seaguard.core.config import get_settings

settings = get_settings()


engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


SessionFactory = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_database_session() -> Generator[Session, None, None]:
    """
    Provide one database session for a FastAPI request.

    The session is closed automatically after the request completes.
    """

    with SessionFactory() as session:
        yield session