from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

SUPPORTED_AIS_SUFFIXES = {
    ".csv",
}


@dataclass(frozen=True)
class DiscoveredAISFile:
    """
    A stable AIS file that is ready for ingestion.

    The SHA-256 digest will later be used by the persistence
    layer to make ingestion restart-safe and idempotent.
    """

    path: Path
    size_bytes: int
    modified_ns: int
    sha256: str

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class _ObservedFileState:
    signature: tuple[int, int]
    stable_scans: int
    emitted_signature: tuple[int, int] | None = None


class DirectoryAISWatcher:
    """
    Detect completed AIS files in an incoming directory.

    Files must remain unchanged for several consecutive scans
    before they are considered ready.

    This prevents SeaGuard from ingesting a CSV while another
    process is still copying or writing it.
    """

    def __init__(
        self,
        directory: str | Path,
        *,
        required_stable_scans: int = 2,
        supported_suffixes: set[str] | None = None,
    ) -> None:
        if required_stable_scans < 1:
            raise ValueError("required_stable_scans must be at least 1.")

        self.directory = Path(directory).expanduser().resolve()

        self.required_stable_scans = required_stable_scans

        self.supported_suffixes = {
            suffix.lower()
            for suffix in (
                supported_suffixes
                if supported_suffixes is not None
                else SUPPORTED_AIS_SUFFIXES
            )
        }

        self._states: dict[
            Path,
            _ObservedFileState,
        ] = {}

    def _is_supported_file(
        self,
        path: Path,
    ) -> bool:
        if not path.is_file():
            return False

        if path.name.startswith("."):
            return False

        return path.suffix.lower() in self.supported_suffixes

    @staticmethod
    def _signature(
        path: Path,
    ) -> tuple[int, int]:
        stat = path.stat()

        return (
            stat.st_size,
            stat.st_mtime_ns,
        )

    @staticmethod
    def _sha256(
        path: Path,
    ) -> str:
        digest = sha256()

        with path.open("rb") as source:
            for chunk in iter(
                lambda: source.read(1024 * 1024),
                b"",
            ):
                digest.update(chunk)

        return digest.hexdigest()

    def _discover_candidates(
        self,
    ) -> list[Path]:
        if not self.directory.exists():
            return []

        return sorted(
            (
                path
                for path in self.directory.iterdir()
                if self._is_supported_file(path)
            ),
            key=lambda path: path.name,
        )

    def scan(
        self,
    ) -> list[DiscoveredAISFile]:
        """
        Scan the directory once and return newly stable files.
        """

        candidates = self._discover_candidates()

        candidate_set = set(candidates)

        stale_paths = [path for path in self._states if path not in candidate_set]

        for path in stale_paths:
            del self._states[path]

        ready: list[DiscoveredAISFile] = []

        for path in candidates:
            try:
                signature = self._signature(path)
            except FileNotFoundError:
                continue

            state = self._states.get(path)

            if state is None:
                state = _ObservedFileState(
                    signature=signature,
                    stable_scans=1,
                )

                self._states[path] = state

            elif state.signature == signature:
                state.stable_scans += 1

            else:
                state.signature = signature

                state.stable_scans = 1

            if state.stable_scans < self.required_stable_scans:
                continue

            if state.emitted_signature == signature:
                continue

            try:
                digest = self._sha256(path)

                signature_after_hash = self._signature(path)
            except FileNotFoundError:
                continue

            # The file changed while it was being hashed.
            # Wait until a later scan before emitting it.
            if signature_after_hash != signature:
                state.signature = signature_after_hash

                state.stable_scans = 1

                continue

            ready.append(
                DiscoveredAISFile(
                    path=path,
                    size_bytes=signature[0],
                    modified_ns=signature[1],
                    sha256=digest,
                )
            )

            state.emitted_signature = signature

        return ready
