from dataclasses import dataclass
from typing import Literal

from seaguard.collision.geometry import CPAResult

CollisionRiskLevel = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


@dataclass(
    frozen=True,
    slots=True,
)
class CollisionRiskThresholds:
    """Thresholds for deterministic collision-risk classification."""

    critical_cpa_nm: float = 0.25
    critical_tcpa_minutes: float = 15.0

    high_cpa_nm: float = 0.50
    high_tcpa_minutes: float = 30.0

    medium_cpa_nm: float = 1.00
    medium_tcpa_minutes: float = 45.0

    def __post_init__(self) -> None:
        values = (
            self.critical_cpa_nm,
            self.critical_tcpa_minutes,
            self.high_cpa_nm,
            self.high_tcpa_minutes,
            self.medium_cpa_nm,
            self.medium_tcpa_minutes,
        )

        if any(value <= 0.0 for value in values):
            raise ValueError("Collision-risk thresholds must be positive.")

        if not (self.critical_cpa_nm <= self.high_cpa_nm <= self.medium_cpa_nm):
            raise ValueError(
                "CPA thresholds must increase from critical to high to medium."
            )

        if not (
            self.critical_tcpa_minutes
            <= self.high_tcpa_minutes
            <= self.medium_tcpa_minutes
        ):
            raise ValueError(
                "TCPA thresholds must increase from critical to high to medium."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class CollisionRiskAssessment:
    """Operator-facing collision encounter assessment."""

    risk_level: CollisionRiskLevel

    current_distance_nm: float
    cpa_distance_nm: float
    tcpa_minutes: float | None

    relative_speed_knots: float
    closing_speed_knots: float

    reasons: tuple[str, ...]


def assess_collision_risk(
    cpa: CPAResult,
    thresholds: CollisionRiskThresholds | None = None,
) -> CollisionRiskAssessment:
    """
    Classify a vessel encounter from CPA/TCPA geometry.

    This is an investigation-priority heuristic.

    It is not a certified collision-avoidance system and does
    not replace COLREGS-compliant navigational judgement.
    """

    thresholds = thresholds or CollisionRiskThresholds()

    reasons: list[str] = []

    #
    # Immediate proximity takes precedence over projected CPA.
    #
    # Even if two vessels have just started diverging, being
    # inside the critical separation threshold is operationally
    # important enough to retain critical priority.
    #
    if cpa.current_distance_nm <= thresholds.critical_cpa_nm:
        reasons.append(
            f"Current vessel separation is within {thresholds.critical_cpa_nm:.2f} NM."
        )

        if cpa.is_closing:
            reasons.append("The vessels are still closing.")
        else:
            reasons.append("The vessels are currently at critical proximity.")

        return CollisionRiskAssessment(
            risk_level="critical",
            current_distance_nm=(cpa.current_distance_nm),
            cpa_distance_nm=(cpa.future_cpa_distance_nm),
            tcpa_minutes=cpa.tcpa_minutes,
            relative_speed_knots=(cpa.relative_speed_knots),
            closing_speed_knots=(cpa.closing_speed_knots),
            reasons=tuple(reasons),
        )

    #
    # Equal/near-equal velocity means there is no meaningful
    # mathematical TCPA under the constant-motion model.
    #
    if cpa.tcpa_minutes is None:
        reasons.append(
            "No meaningful TCPA exists because relative vessel motion is negligible."
        )

        return CollisionRiskAssessment(
            risk_level="low",
            current_distance_nm=(cpa.current_distance_nm),
            cpa_distance_nm=(cpa.future_cpa_distance_nm),
            tcpa_minutes=None,
            relative_speed_knots=(cpa.relative_speed_knots),
            closing_speed_knots=(cpa.closing_speed_knots),
            reasons=tuple(reasons),
        )

    #
    # A negative or zero TCPA indicates that the mathematical
    # closest point is now or has already occurred.
    #
    if cpa.tcpa_minutes <= 0.0 or not cpa.is_closing:
        reasons.append("The vessels are not on a future closing encounter.")

        if cpa.tcpa_minutes < 0.0:
            reasons.append(
                "The mathematical closest point of approach has already occurred."
            )

        return CollisionRiskAssessment(
            risk_level="low",
            current_distance_nm=(cpa.current_distance_nm),
            cpa_distance_nm=(cpa.future_cpa_distance_nm),
            tcpa_minutes=(cpa.tcpa_minutes),
            relative_speed_knots=(cpa.relative_speed_knots),
            closing_speed_knots=(cpa.closing_speed_knots),
            reasons=tuple(reasons),
        )

    future_cpa_nm = cpa.future_cpa_distance_nm

    tcpa_minutes = cpa.tcpa_minutes

    if (
        future_cpa_nm <= thresholds.critical_cpa_nm
        and tcpa_minutes <= thresholds.critical_tcpa_minutes
    ):
        risk_level: CollisionRiskLevel = "critical"

        reasons.append(
            f"Projected closest approach is within {thresholds.critical_cpa_nm:.2f} NM."
        )

        reasons.append(
            "The projected closest approach occurs within "
            f"{thresholds.critical_tcpa_minutes:.0f} minutes."
        )

    elif (
        future_cpa_nm <= thresholds.high_cpa_nm
        and tcpa_minutes <= thresholds.high_tcpa_minutes
    ):
        risk_level = "high"

        reasons.append(
            f"Projected closest approach is within {thresholds.high_cpa_nm:.2f} NM."
        )

        reasons.append(
            "The projected closest approach occurs within "
            f"{thresholds.high_tcpa_minutes:.0f} minutes."
        )

    elif (
        future_cpa_nm <= thresholds.medium_cpa_nm
        and tcpa_minutes <= thresholds.medium_tcpa_minutes
    ):
        risk_level = "medium"

        reasons.append(
            f"Projected closest approach is within {thresholds.medium_cpa_nm:.2f} NM."
        )

        reasons.append(
            "The projected closest approach occurs within "
            f"{thresholds.medium_tcpa_minutes:.0f} minutes."
        )

    else:
        risk_level = "low"

        reasons.append(
            "Projected CPA/TCPA does not meet the configured "
            "elevated collision-risk thresholds."
        )

    if risk_level != "low":
        reasons.append(
            f"The vessels are closing at {cpa.closing_speed_knots:.2f} knots."
        )

    return CollisionRiskAssessment(
        risk_level=risk_level,
        current_distance_nm=(cpa.current_distance_nm),
        cpa_distance_nm=(future_cpa_nm),
        tcpa_minutes=(tcpa_minutes),
        relative_speed_knots=(cpa.relative_speed_knots),
        closing_speed_knots=(cpa.closing_speed_knots),
        reasons=tuple(reasons),
    )
