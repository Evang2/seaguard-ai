from collections.abc import Iterable
from dataclasses import dataclass

from seaguard.collision.candidates import (
    EncounterCandidateSearchResult,
    EncounterVessel,
    generate_encounter_candidates,
)
from seaguard.collision.geometry import (
    CPAResult,
    calculate_cpa_tcpa,
)
from seaguard.collision.risk import (
    CollisionRiskAssessment,
    CollisionRiskThresholds,
    assess_collision_risk,
)

RISK_PRIORITY = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


@dataclass(frozen=True, slots=True)
class CollisionEncounter:
    """Evaluated encounter between two vessels."""

    vessel_a: EncounterVessel
    vessel_b: EncounterVessel
    cpa: CPAResult
    risk: CollisionRiskAssessment


@dataclass(frozen=True, slots=True)
class CollisionScanResult:
    """Result of evaluating one vessel snapshot."""

    encounters: tuple[CollisionEncounter, ...]
    candidate_search: EncounterCandidateSearchResult
    assessed_candidate_count: int
    include_low: bool

    @property
    def encounter_count(self) -> int:
        return len(self.encounters)

    @property
    def critical_count(self) -> int:
        return sum(
            encounter.risk.risk_level == "critical" for encounter in self.encounters
        )

    @property
    def high_count(self) -> int:
        return sum(encounter.risk.risk_level == "high" for encounter in self.encounters)

    @property
    def medium_count(self) -> int:
        return sum(
            encounter.risk.risk_level == "medium" for encounter in self.encounters
        )

    @property
    def low_count(self) -> int:
        return sum(encounter.risk.risk_level == "low" for encounter in self.encounters)


def _tcpa_sort_value(
    encounter: CollisionEncounter,
) -> float:
    """
    Return TCPA value suitable for sorting.

    Encounters without a meaningful future TCPA are placed last.
    """

    tcpa_minutes = encounter.risk.tcpa_minutes

    if tcpa_minutes is None:
        return float("inf")

    if tcpa_minutes < 0.0:
        return float("inf")

    return tcpa_minutes


def evaluate_collision_encounters(
    vessels: Iterable[EncounterVessel],
    *,
    max_distance_nm: float = 5.0,
    thresholds: CollisionRiskThresholds | None = None,
    include_low: bool = False,
) -> CollisionScanResult:
    """
    Evaluate collision risk for one vessel-position snapshot.

    Processing stages:

    1. Geographic candidate generation.
    2. CPA/TCPA relative-motion calculation.
    3. Deterministic collision-risk classification.
    4. Optional removal of LOW-risk encounters.

    Results are ordered by:

    CRITICAL
    HIGH
    MEDIUM
    LOW

    followed by earliest future TCPA and then smallest CPA.
    """

    candidate_search = generate_encounter_candidates(
        vessels,
        max_distance_nm=max_distance_nm,
    )

    encounters: list[CollisionEncounter] = []

    for candidate in candidate_search.candidates:
        cpa = calculate_cpa_tcpa(
            candidate.vessel_a.to_motion(),
            candidate.vessel_b.to_motion(),
        )

        risk = assess_collision_risk(
            cpa,
            thresholds,
        )

        if not include_low and risk.risk_level == "low":
            continue

        encounters.append(
            CollisionEncounter(
                vessel_a=candidate.vessel_a,
                vessel_b=candidate.vessel_b,
                cpa=cpa,
                risk=risk,
            )
        )

    encounters.sort(
        key=lambda encounter: (
            RISK_PRIORITY[encounter.risk.risk_level],
            _tcpa_sort_value(
                encounter,
            ),
            encounter.risk.cpa_distance_nm,
            encounter.vessel_a.mmsi,
            encounter.vessel_b.mmsi,
        ),
    )

    return CollisionScanResult(
        encounters=tuple(encounters),
        candidate_search=candidate_search,
        assessed_candidate_count=(candidate_search.candidate_count),
        include_low=include_low,
    )
