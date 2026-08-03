from logging.config import fileConfig
from typing import Any

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import engine_from_config, pool

from seaguard.core.config import get_settings
from seaguard.db import models  # noqa: F401
from seaguard.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


settings = get_settings()

config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("%", "%%"),
)


target_metadata = Base.metadata


def include_object(
    object_: Any,
    name: str | None,
    object_type: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    """
    Exclude database objects that are not managed by SeaGuard.

    PostGIS installs internal tables such as spatial_ref_sys,
    tiger geocoder tables, and topology tables. Alembic must not
    generate DROP operations for those extension-owned objects.
    """

    if object_type == "table" and reflected and compare_to is None:
        return False

    return alembic_helpers.include_object(
        object_,
        name,
        object_type,
        reflected,
        compare_to,
    )


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
        include_object=include_object,
        process_revision_directives=(alembic_helpers.writer),
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using an active database connection."""

    configuration = config.get_section(
        config.config_ini_section,
        {},
    )

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
            process_revision_directives=(alembic_helpers.writer),
            render_item=alembic_helpers.render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
