from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

RULE_COLUMNS = [
    "flag_reporting_gap",
    "flag_position_jump",
    "flag_speed_mismatch",
    "flag_rapid_course_change",
    "flag_rapid_heading_change",
    "flag_extreme_acceleration",
    "flag_nonpositive_interval",
]

WARNING_RULES = [
    "flag_reporting_gap",
    "flag_rapid_course_change",
    "flag_rapid_heading_change",
]

HIGH_RULES = [
    "flag_speed_mismatch",
    "flag_extreme_acceleration",
    "flag_nonpositive_interval",
]

CRITICAL_RULES = [
    "flag_position_jump",
]


@dataclass(frozen=True, slots=True)
class HybridRiskThresholds:
    """
    Percentile thresholds used by the hybrid risk classifier.

    Percentiles describe how unusual an Isolation Forest score is relative
    to the fitted reference score distribution. They are not probabilities.
    """

    elevated_ml_percentile: float = 95.0
    high_ml_percentile: float = 98.0
    very_high_ml_percentile: float = 99.0
    extreme_ml_percentile: float = 99.5


def _boolean_column(
    dataframe: pd.DataFrame,
    column: str,
) -> pd.Series:
    """Return a normalized Boolean column."""

    if column not in dataframe.columns:
        raise ValueError(
            f"Missing required rule column: {column}",
        )

    values = dataframe[column]

    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)

    return values.astype("string").str.strip().str.lower().isin({"true", "1", "yes"})


class HybridRiskAssessor:
    """
    Combine deterministic AIS rule evidence with Isolation Forest ranking.

    The classifier intentionally uses the ML anomaly score as a relative
    ranking signal rather than treating it as a probability.
    """

    def __init__(
        self,
        thresholds: HybridRiskThresholds | None = None,
    ) -> None:
        self.thresholds = (
            thresholds if thresholds is not None else HybridRiskThresholds()
        )

        self._reference_scores: np.ndarray | None = None

    @property
    def is_fitted(self) -> bool:
        """Return whether a reference ML score distribution is available."""

        return self._reference_scores is not None

    def fit(
        self,
        reference: pd.DataFrame | pd.Series,
    ) -> HybridRiskAssessor:
        """
        Fit the percentile calibration using reference ML anomaly scores.

        A DataFrame must contain ``ml_anomaly_score``. A Series is interpreted
        directly as anomaly scores.
        """

        if isinstance(reference, pd.DataFrame):
            if "ml_anomaly_score" not in reference.columns:
                raise ValueError(
                    "Reference DataFrame must contain ml_anomaly_score.",
                )

            scores = reference["ml_anomaly_score"]
        else:
            scores = reference

        numeric_scores = pd.to_numeric(
            scores,
            errors="coerce",
        )

        numeric_scores = numeric_scores.replace(
            [np.inf, -np.inf],
            np.nan,
        ).dropna()

        if numeric_scores.empty:
            raise ValueError(
                "Cannot fit hybrid risk calibration because "
                "no valid ML anomaly scores are available.",
            )

        self._reference_scores = np.sort(
            numeric_scores.to_numpy(
                dtype=float,
            ),
        )

        return self

    def _percentiles(
        self,
        scores: pd.Series,
    ) -> pd.Series:
        """Convert raw ML scores into reference-distribution percentiles."""

        if self._reference_scores is None:
            raise RuntimeError(
                "HybridRiskAssessor must be fitted before assessment.",
            )

        numeric_scores = pd.to_numeric(
            scores,
            errors="coerce",
        )

        output = pd.Series(
            np.nan,
            index=scores.index,
            dtype="float64",
        )

        valid = numeric_scores.notna()

        values = numeric_scores.loc[valid].to_numpy(
            dtype=float,
        )

        ranks = np.searchsorted(
            self._reference_scores,
            values,
            side="right",
        )

        output.loc[valid] = 100.0 * ranks / len(self._reference_scores)

        return output

    def assess(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Add explainable hybrid risk fields to AIS observations.

        Added columns:
        - ml_anomaly_percentile
        - rule_flag_count
        - rule_severity
        - detector_agreement
        - risk_level
        - risk_reasons
        """

        if not self.is_fitted:
            raise RuntimeError(
                "HybridRiskAssessor must be fitted before assessment.",
            )

        if "ml_anomaly_score" not in dataframe.columns:
            raise ValueError(
                "Input DataFrame must contain ml_anomaly_score.",
            )

        result = dataframe.copy()

        normalized_rules: dict[str, pd.Series] = {}

        for column in RULE_COLUMNS:
            normalized = _boolean_column(
                result,
                column,
            )

            result[column] = normalized
            normalized_rules[column] = normalized

        result["rule_flag_count"] = result[RULE_COLUMNS].sum(axis=1).astype(int)

        has_warning_rule = result[WARNING_RULES].any(axis=1)

        has_high_rule = result[HIGH_RULES].any(axis=1)

        has_critical_rule = result[CRITICAL_RULES].any(axis=1)

        rule_severity = pd.Series(
            "none",
            index=result.index,
            dtype="string",
        )

        rule_severity.loc[has_warning_rule] = "warning"

        rule_severity.loc[has_high_rule] = "high"

        rule_severity.loc[has_critical_rule] = "critical"

        result["rule_severity"] = rule_severity

        ml_percentile = self._percentiles(
            result["ml_anomaly_score"],
        )

        result["ml_anomaly_percentile"] = ml_percentile

        elevated_ml = ml_percentile.ge(
            self.thresholds.elevated_ml_percentile,
        )

        high_ml = ml_percentile.ge(
            self.thresholds.high_ml_percentile,
        )

        very_high_ml = ml_percentile.ge(
            self.thresholds.very_high_ml_percentile,
        )

        extreme_ml = ml_percentile.ge(
            self.thresholds.extreme_ml_percentile,
        )

        has_rule = result["rule_flag_count"] > 0

        result["detector_agreement"] = has_rule & elevated_ml.fillna(False)

        risk_level = pd.Series(
            "low",
            index=result.index,
            dtype="string",
        )

        medium_mask = has_rule | elevated_ml.fillna(False)

        risk_level.loc[medium_mask] = "medium"

        high_mask = (
            has_high_rule
            | extreme_ml.fillna(False)
            | (high_ml.fillna(False) & has_rule)
        )

        risk_level.loc[high_mask] = "high"

        critical_mask = (
            has_critical_rule
            | (very_high_ml.fillna(False) & (result["rule_flag_count"] >= 2))
            | (extreme_ml.fillna(False) & has_high_rule)
        )

        risk_level.loc[critical_mask] = "critical"

        result["risk_level"] = risk_level

        reasons: list[str] = []

        for index in result.index:
            row_reasons: list[str] = []

            active_rule_names = [
                column.removeprefix("flag_")
                for column, values in normalized_rules.items()
                if bool(values.loc[index])
            ]

            if active_rule_names:
                row_reasons.append(
                    "rules="
                    + ",".join(
                        active_rule_names,
                    )
                )

            percentile = ml_percentile.loc[index]

            if pd.notna(percentile) and (
                percentile >= self.thresholds.elevated_ml_percentile
            ):
                row_reasons.append(f"ml_percentile={percentile:.2f}")

            if not row_reasons:
                row_reasons.append(
                    "no_elevated_evidence",
                )

            reasons.append(
                "; ".join(
                    row_reasons,
                )
            )

        result["risk_reasons"] = reasons

        return result

    def fit_assess(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """Fit score calibration and assess the same DataFrame."""

        self.fit(
            dataframe,
        )

        return self.assess(
            dataframe,
        )
