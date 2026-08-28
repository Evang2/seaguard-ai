"""add ingestion identity to import jobs

Revision ID: 9f3c2d1a7b44
Revises: 7ecc618b4b96
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f3c2d1a7b44"
down_revision: str | Sequence[str] | None = "7ecc618b4b96"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_jobs",
        sa.Column(
            "content_sha256",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "import_jobs",
        sa.Column(
            "file_size_bytes",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    # PostgreSQL permits multiple NULL values in a
    # unique index. Existing historical import jobs
    # therefore remain valid.
    op.create_index(
        "ux_import_jobs_content_sha256",
        "import_jobs",
        ["content_sha256"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_import_jobs_content_sha256",
        table_name="import_jobs",
    )

    op.drop_column(
        "import_jobs",
        "file_size_bytes",
    )

    op.drop_column(
        "import_jobs",
        "content_sha256",
    )
