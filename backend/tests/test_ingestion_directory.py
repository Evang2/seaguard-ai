from hashlib import sha256
from pathlib import Path

import pytest

from seaguard.ingestion.directory import (
    DirectoryAISWatcher,
)


def write_file(
    path: Path,
    content: str,
) -> None:
    path.write_text(
        content,
        encoding="utf-8",
    )


def test_requires_at_least_one_stable_scan(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="at least 1",
    ):
        DirectoryAISWatcher(
            tmp_path,
            required_stable_scans=0,
        )


def test_missing_directory_returns_no_files(
    tmp_path: Path,
) -> None:
    watcher = DirectoryAISWatcher(
        tmp_path / "missing",
    )

    assert watcher.scan() == []


def test_unsupported_files_are_ignored(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "notes.txt",
        "not AIS data",
    )

    watcher = DirectoryAISWatcher(
        tmp_path,
        required_stable_scans=1,
    )

    assert watcher.scan() == []


def test_hidden_files_are_ignored(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / ".partial.csv",
        "mmsi,timestamp\n",
    )

    watcher = DirectoryAISWatcher(
        tmp_path,
        required_stable_scans=1,
    )

    assert watcher.scan() == []


def test_csv_becomes_ready_after_stable_scans(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ais_batch.csv"

    content = "mmsi,timestamp\n123456789,2024-06-14T12:00:00Z\n"

    write_file(
        path,
        content,
    )

    watcher = DirectoryAISWatcher(
        tmp_path,
        required_stable_scans=2,
    )

    assert watcher.scan() == []

    ready = watcher.scan()

    assert len(ready) == 1

    discovered = ready[0]

    assert discovered.path == path
    assert discovered.name == ("ais_batch.csv")
    assert discovered.size_bytes == (path.stat().st_size)
    assert discovered.sha256 == (sha256(content.encode("utf-8")).hexdigest())


def test_same_file_is_not_emitted_repeatedly(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ais_batch.csv"

    write_file(
        path,
        "mmsi,timestamp\n",
    )

    watcher = DirectoryAISWatcher(
        tmp_path,
        required_stable_scans=2,
    )

    assert watcher.scan() == []

    assert len(watcher.scan()) == 1

    assert watcher.scan() == []
    assert watcher.scan() == []


def test_changed_file_can_be_emitted_again(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ais_batch.csv"

    write_file(
        path,
        "mmsi,timestamp\n",
    )

    watcher = DirectoryAISWatcher(
        tmp_path,
        required_stable_scans=2,
    )

    watcher.scan()

    first_ready = watcher.scan()

    assert len(first_ready) == 1

    write_file(
        path,
        ("mmsi,timestamp\n123456789,2024-06-14T12:00:00Z\n"),
    )

    assert watcher.scan() == []

    second_ready = watcher.scan()

    assert len(second_ready) == 1

    assert second_ready[0].sha256 != first_ready[0].sha256


def test_ready_files_are_sorted_by_name(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "z.csv",
        "z",
    )

    write_file(
        tmp_path / "a.csv",
        "a",
    )

    watcher = DirectoryAISWatcher(
        tmp_path,
        required_stable_scans=1,
    )

    ready = watcher.scan()

    assert [item.name for item in ready] == [
        "a.csv",
        "z.csv",
    ]
