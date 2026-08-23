from collections.abc import Iterable
from dataclasses import dataclass
from math import asin, cos, degrees, isfinite, radians, sin, sqrt

from seaguard.collision.geometry import VesselMotion

EARTH_RADIUS_NM = 3440.065


@dataclass(frozen=True, slots=True)
class EncounterVessel:
    """Current vessel state used for encounter scanning."""

    mmsi: str
    latitude: float
    longitude: float
    sog_knots: float
    cog_degrees: float

    def to_motion(self) -> VesselMotion:
        return VesselMotion(
            latitude=self.latitude,
            longitude=self.longitude,
            sog_knots=self.sog_knots,
            cog_degrees=self.cog_degrees,
        )


@dataclass(frozen=True, slots=True)
class EncounterCandidate:
    """Nearby vessel pair worth evaluating with CPA/TCPA."""

    vessel_a: EncounterVessel
    vessel_b: EncounterVessel
    current_distance_nm: float


@dataclass(frozen=True, slots=True)
class EncounterCandidateSearchResult:
    """Result and metrics from the geographic candidate search."""

    candidates: tuple[EncounterCandidate, ...]

    vessel_count: int
    possible_pair_count: int
    distance_checked_pair_count: int

    max_distance_nm: float

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


def _validate_vessel(
    vessel: EncounterVessel,
) -> None:
    if not vessel.mmsi.strip():
        raise ValueError("Vessel MMSI cannot be empty.")

    values = (
        vessel.latitude,
        vessel.longitude,
        vessel.sog_knots,
        vessel.cog_degrees,
    )

    if not all(isfinite(value) for value in values):
        raise ValueError("Encounter vessel values must be finite numbers.")

    if not (-90.0 <= vessel.latitude <= 90.0):
        raise ValueError("Latitude must be between -90 and 90 degrees.")

    if not (-180.0 <= vessel.longitude <= 180.0):
        raise ValueError("Longitude must be between -180 and 180 degrees.")

    if vessel.sog_knots < 0.0:
        raise ValueError("Speed over ground cannot be negative.")


def _great_circle_distance_nm(
    vessel_a: EncounterVessel,
    vessel_b: EncounterVessel,
) -> float:
    """
    Calculate great-circle distance using the haversine formula.

    This is used only as a geographic proximity filter before
    the more detailed relative-motion CPA/TCPA calculation.
    """

    latitude_a = radians(
        vessel_a.latitude,
    )

    latitude_b = radians(
        vessel_b.latitude,
    )

    latitude_difference = latitude_b - latitude_a

    longitude_difference = radians(
        vessel_b.longitude - vessel_a.longitude,
    )

    half_latitude_sine = sin(
        latitude_difference / 2.0,
    )

    half_longitude_sine = sin(
        longitude_difference / 2.0,
    )

    haversine = (
        half_latitude_sine**2
        + cos(latitude_a) * cos(latitude_b) * half_longitude_sine**2
    )

    haversine = min(
        1.0,
        max(
            0.0,
            haversine,
        ),
    )

    angular_distance = 2.0 * asin(
        sqrt(haversine),
    )

    return EARTH_RADIUS_NM * angular_distance


def _canonical_pair(
    vessel_a: EncounterVessel,
    vessel_b: EncounterVessel,
) -> tuple[
    EncounterVessel,
    EncounterVessel,
]:
    """
    Give every vessel pair a deterministic MMSI ordering.

    This prevents A/B and B/A from being treated as different
    encounter identities later when persistence is introduced.
    """

    if vessel_a.mmsi <= vessel_b.mmsi:
        return (
            vessel_a,
            vessel_b,
        )

    return (
        vessel_b,
        vessel_a,
    )


def generate_encounter_candidates(
    vessels: Iterable[EncounterVessel],
    *,
    max_distance_nm: float = 5.0,
) -> EncounterCandidateSearchResult:
    """
    Find vessel pairs close enough for CPA/TCPA evaluation.

    A latitude sweep is used as a cheap first-stage filter.

    Only pairs whose latitude separation could possibly fall
    inside the configured search radius receive the more
    expensive great-circle distance calculation.
    """

    if not isfinite(max_distance_nm) or max_distance_nm <= 0.0:
        raise ValueError("Maximum encounter distance must be a positive finite number.")

    vessel_list = list(
        vessels,
    )

    seen_mmsi: set[str] = set()

    for vessel in vessel_list:
        _validate_vessel(
            vessel,
        )

        if vessel.mmsi in seen_mmsi:
            raise ValueError(
                "Encounter candidate input must contain "
                f"only one state per MMSI: {vessel.mmsi}."
            )

        seen_mmsi.add(
            vessel.mmsi,
        )

    vessel_count = len(
        vessel_list,
    )

    possible_pair_count = vessel_count * (vessel_count - 1) // 2

    if vessel_count < 2:
        return EncounterCandidateSearchResult(
            candidates=(),
            vessel_count=vessel_count,
            possible_pair_count=(possible_pair_count),
            distance_checked_pair_count=0,
            max_distance_nm=(max_distance_nm),
        )

    sorted_vessels = sorted(
        vessel_list,
        key=lambda vessel: (
            vessel.latitude,
            vessel.mmsi,
        ),
    )

    #
    # A great-circle distance cannot be smaller than the
    # north/south angular separation alone.
    #
    # This lets us stop scanning forward once the latitude
    # difference already exceeds the search radius.
    #
    maximum_latitude_difference = degrees(max_distance_nm / EARTH_RADIUS_NM)

    candidates: list[EncounterCandidate] = []

    distance_checked_pair_count = 0

    for index, vessel_a in enumerate(
        sorted_vessels,
    ):
        for vessel_b in sorted_vessels[index + 1 :]:
            latitude_difference = vessel_b.latitude - vessel_a.latitude

            if latitude_difference > maximum_latitude_difference:
                break

            distance_checked_pair_count += 1

            distance_nm = _great_circle_distance_nm(
                vessel_a,
                vessel_b,
            )

            if distance_nm > max_distance_nm:
                continue

            (
                canonical_a,
                canonical_b,
            ) = _canonical_pair(
                vessel_a,
                vessel_b,
            )

            candidates.append(
                EncounterCandidate(
                    vessel_a=(canonical_a),
                    vessel_b=(canonical_b),
                    current_distance_nm=(distance_nm),
                )
            )

    candidates.sort(
        key=lambda candidate: (
            candidate.current_distance_nm,
            candidate.vessel_a.mmsi,
            candidate.vessel_b.mmsi,
        ),
    )

    return EncounterCandidateSearchResult(
        candidates=tuple(
            candidates,
        ),
        vessel_count=vessel_count,
        possible_pair_count=(possible_pair_count),
        distance_checked_pair_count=(distance_checked_pair_count),
        max_distance_nm=(max_distance_nm),
    )
