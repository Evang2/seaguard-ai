from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from seaguard.ingestion.directory import DiscoveredAISFile
from seaguard.ingestion.registry import (
    claim_ingestion_file,
    complete_ingestion_job,
    fail_ingestion_job,
)


def create_test_session() -> Session:
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE import_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_file TEXT NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    rows_read INTEGER NOT NULL DEFAULT 0,
                    rows_imported INTEGER NOT NULL DEFAULT 0,
                    rows_rejected INTEGER NOT NULL DEFAULT 0,
                    duplicates_skipped INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NULL,
                    started_at DATETIME NOT NULL,
                    finished_at DATETIME NULL,
                    content_sha256 VARCHAR(64) NULL UNIQUE,
                    file_size_bytes INTEGER NULL
                )
                """
            )
        )

    return Session(engine)


def discovered_file(
    digest: str = "a" * 64,
) -> DiscoveredAISFile:
    return DiscoveredAISFile(
        path=Path("/tmp/example.csv"),
        size_bytes=1234,
        modified_ns=1,
        sha256=digest,
    )


def test_new_file_should_be_processed() -> None:
    session = create_test_session()

    try:
        claim = claim_ingestion_file(
            session,
            discovered_file(),
        )

        assert claim.should_process
        assert claim.previous_status == "pending"

        row = session.execute(
            text(
                """
                SELECT *
                FROM import_jobs
                WHERE id = :job_id
                """
            ),
            {
                "job_id": claim.job_id,
            },
        ).one()

        assert row.content_sha256 == "a" * 64
        assert row.file_size_bytes == 1234
        assert row.status == "pending"

    finally:
        session.close()


def test_completed_file_is_skipped() -> None:
    session = create_test_session()

    try:
        first_claim = claim_ingestion_file(
            session,
            discovered_file(),
        )

        complete_ingestion_job(
            session,
            first_claim.job_id,
            rows_read=10,
            rows_imported=8,
            rows_rejected=1,
            duplicates_skipped=1,
        )

        second_claim = claim_ingestion_file(
            session,
            discovered_file(),
        )

        assert not second_claim.should_process
        assert second_claim.job_id == first_claim.job_id
        assert second_claim.previous_status == "completed"

        count = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM import_jobs
                """
            )
        ).scalar_one()

        assert count == 1

    finally:
        session.close()


def test_failed_file_can_be_retried() -> None:
    session = create_test_session()

    try:
        first_claim = claim_ingestion_file(
            session,
            discovered_file(),
        )

        fail_ingestion_job(
            session,
            first_claim.job_id,
            "bad CSV",
        )

        second_claim = claim_ingestion_file(
            session,
            discovered_file(),
        )

        assert second_claim.should_process

        assert second_claim.previous_status == "failed"

        assert second_claim.job_id == first_claim.job_id

        row = session.execute(
            text(
                """
                SELECT
                    status,
                    error_message,
                    finished_at
                FROM import_jobs
                WHERE id = :job_id
                """
            ),
            {
                "job_id": first_claim.job_id,
            },
        ).one()

        assert row.status == "pending"
        assert row.error_message is None
        assert row.finished_at is None

    finally:
        session.close()


def test_pending_job_survives_worker_restart() -> None:
    session = create_test_session()

    try:
        first_claim = claim_ingestion_file(
            session,
            discovered_file(),
        )

        # Simulate the worker disappearing before completion.
        second_claim = claim_ingestion_file(
            session,
            discovered_file(),
        )

        assert second_claim.should_process
        assert second_claim.job_id == first_claim.job_id
        assert second_claim.previous_status == "pending"

    finally:
        session.close()


def test_different_hash_creates_new_job() -> None:
    session = create_test_session()

    try:
        first = claim_ingestion_file(
            session,
            discovered_file("a" * 64),
        )

        second = claim_ingestion_file(
            session,
            discovered_file("b" * 64),
        )

        assert first.job_id != second.job_id

        count = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM import_jobs
                """
            )
        ).scalar_one()

        assert count == 2

    finally:
        session.close()
