from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

ALERT_COLUMNS = [
    "mmsi",
    "timestamp",
    "latitude",
    "longitude",
    "anomaly_type",
    "severity",
    "metric_name",
    "metric_value",
    "threshold",
    "message",
]


@dataclass(frozen=True, slots=True)
class AnomalyThresholds:
    """Configurable thresholds for rule-based AIS detection."""

    reporting_gap_minutes: float = 15.0
    position_jump_speed_knots: float = 60.0
    speed_difference_knots: float = 15.0
    course_change_degrees: float = 90.0
    heading_change_degrees: float = 90.0
    maximum_turn_interval_minutes: float = 10.0
    minimum_turn_speed_knots: float = 3.0
    acceleration_knots_per_minute: float = 2.0


def _numeric_column(
    dataframe: pd.DataFrame,
    column: str,
) -> pd.Series:
    """Return a numeric column or an empty numeric series."""

    if column not in dataframe.columns:
        return pd.Series(
            float("nan"),
            index=dataframe.index,
            dtype="float64",
        )

    return pd.to_numeric(
        dataframe[column],
        errors="coerce",
    )


def _boolean_column(
    dataframe: pd.DataFrame,
    column: str,
) -> pd.Series:
    """Return a normalized Boolean column."""

    if column not in dataframe.columns:
        return pd.Series(
            False,
            index=dataframe.index,
            dtype="bool",
        )

    values = dataframe[column]

    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)

    return values.astype("string").str.strip().str.lower().isin({"true", "1", "yes"})


def detect_rule_based_anomalies(
    source: pd.DataFrame,
    thresholds: AnomalyThresholds | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Add rule-based anomaly flags and create explainable alerts.

    Returns:
        A tuple containing:
        1. The trajectory DataFrame with anomaly columns.
        2. One alert row for every triggered anomaly.
    """

    required_columns = {
        "mmsi",
        "timestamp",
    }

    missing_columns = required_columns - set(source.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise ValueError(f"Missing required anomaly columns: {missing}")

    active_thresholds = thresholds or AnomalyThresholds()

    annotated = source.copy()

    annotated["mmsi"] = (
        annotated["mmsi"].astype("string").str.replace(r"\.0$", "", regex=True)
    )

    annotated["timestamp"] = pd.to_datetime(
        annotated["timestamp"],
        errors="coerce",
        utc=True,
    )

    reporting_gap = _numeric_column(
        annotated,
        "reporting_gap_minutes",
    )

    calculated_speed = _numeric_column(
        annotated,
        "calculated_speed_knots",
    )

    speed_difference = _numeric_column(
        annotated,
        "speed_difference_knots",
    ).abs()

    course_change = _numeric_column(
        annotated,
        "course_change_degrees",
    )

    heading_change = _numeric_column(
        annotated,
        "heading_change_degrees",
    )

    acceleration = _numeric_column(
        annotated,
        "acceleration_knots_per_minute",
    ).abs()

    reported_speed = _numeric_column(
        annotated,
        "sog",
    )

    elapsed_seconds = _numeric_column(
        annotated,
        "elapsed_seconds",
    )

    existing_nonpositive_interval = _boolean_column(
        annotated,
        "nonpositive_time_interval",
    )

    turn_interval_is_short = reporting_gap.le(
        active_thresholds.maximum_turn_interval_minutes
    )

    vessel_is_moving = reported_speed.ge(active_thresholds.minimum_turn_speed_knots)

    annotated["flag_reporting_gap"] = reporting_gap.gt(
        active_thresholds.reporting_gap_minutes
    ).fillna(False)

    annotated["flag_position_jump"] = calculated_speed.gt(
        active_thresholds.position_jump_speed_knots
    ).fillna(False)

    annotated["flag_speed_mismatch"] = speed_difference.gt(
        active_thresholds.speed_difference_knots
    ).fillna(False)

    annotated["flag_rapid_course_change"] = (
        course_change.gt(active_thresholds.course_change_degrees)
        & turn_interval_is_short
        & vessel_is_moving
    ).fillna(False)

    annotated["flag_rapid_heading_change"] = (
        heading_change.gt(active_thresholds.heading_change_degrees)
        & turn_interval_is_short
        & vessel_is_moving
    ).fillna(False)

    annotated["flag_extreme_acceleration"] = acceleration.gt(
        active_thresholds.acceleration_knots_per_minute
    ).fillna(False)

    annotated["flag_nonpositive_interval"] = (
        existing_nonpositive_interval | elapsed_seconds.le(0).fillna(False)
    )

    flag_columns = [
        "flag_reporting_gap",
        "flag_position_jump",
        "flag_speed_mismatch",
        "flag_rapid_course_change",
        "flag_rapid_heading_change",
        "flag_extreme_acceleration",
        "flag_nonpositive_interval",
    ]

    anomaly_names = {
        "flag_reporting_gap": "reporting_gap",
        "flag_position_jump": "position_jump",
        "flag_speed_mismatch": "speed_mismatch",
        "flag_rapid_course_change": "rapid_course_change",
        "flag_rapid_heading_change": "rapid_heading_change",
        "flag_extreme_acceleration": "extreme_acceleration",
        "flag_nonpositive_interval": "nonpositive_interval",
    }

    annotated["anomaly_count"] = annotated[flag_columns].sum(axis=1).astype(int)

    annotated["has_anomaly"] = annotated["anomaly_count"] > 0

    annotated["anomaly_types"] = annotated.apply(
        lambda row: ",".join(
            anomaly_names[column] for column in flag_columns if bool(row[column])
        ),
        axis=1,
    )

    alerts: list[dict[str, object]] = []

    def add_alerts(
        mask: pd.Series,
        *,
        anomaly_type: str,
        severity: str,
        metric_name: str,
        metric_values: pd.Series,
        threshold: float,
        description: str,
    ) -> None:
        """Append alert records for every matching observation."""

        for index in annotated.index[mask]:
            metric_value = metric_values.loc[index]

            latitude = (
                annotated.at[index, "latitude"]
                if "latitude" in annotated.columns
                else None
            )

            longitude = (
                annotated.at[index, "longitude"]
                if "longitude" in annotated.columns
                else None
            )

            alerts.append(
                {
                    "mmsi": annotated.at[index, "mmsi"],
                    "timestamp": annotated.at[
                        index,
                        "timestamp",
                    ],
                    "latitude": (float(latitude) if pd.notna(latitude) else None),
                    "longitude": (float(longitude) if pd.notna(longitude) else None),
                    "anomaly_type": anomaly_type,
                    "severity": severity,
                    "metric_name": metric_name,
                    "metric_value": (
                        float(metric_value) if pd.notna(metric_value) else None
                    ),
                    "threshold": threshold,
                    "message": description.format(
                        value=metric_value,
                        threshold=threshold,
                    ),
                }
            )

    add_alerts(
        annotated["flag_reporting_gap"],
        anomaly_type="reporting_gap",
        severity="warning",
        metric_name="reporting_gap_minutes",
        metric_values=reporting_gap,
        threshold=active_thresholds.reporting_gap_minutes,
        description=(
            "AIS reporting gap was {value:.2f} minutes, "
            "exceeding the {threshold:.2f}-minute threshold."
        ),
    )

    add_alerts(
        annotated["flag_position_jump"],
        anomaly_type="position_jump",
        severity="critical",
        metric_name="calculated_speed_knots",
        metric_values=calculated_speed,
        threshold=active_thresholds.position_jump_speed_knots,
        description=(
            "Position change implies {value:.2f} knots, "
            "exceeding the {threshold:.2f}-knot threshold."
        ),
    )

    add_alerts(
        annotated["flag_speed_mismatch"],
        anomaly_type="speed_mismatch",
        severity="high",
        metric_name="speed_difference_knots",
        metric_values=speed_difference,
        threshold=active_thresholds.speed_difference_knots,
        description=(
            "Calculated and reported speed differed by "
            "{value:.2f} knots, exceeding the "
            "{threshold:.2f}-knot threshold."
        ),
    )

    add_alerts(
        annotated["flag_rapid_course_change"],
        anomaly_type="rapid_course_change",
        severity="warning",
        metric_name="course_change_degrees",
        metric_values=course_change,
        threshold=active_thresholds.course_change_degrees,
        description=(
            "Course changed by {value:.2f} degrees, "
            "exceeding the {threshold:.2f}-degree threshold."
        ),
    )

    add_alerts(
        annotated["flag_rapid_heading_change"],
        anomaly_type="rapid_heading_change",
        severity="warning",
        metric_name="heading_change_degrees",
        metric_values=heading_change,
        threshold=active_thresholds.heading_change_degrees,
        description=(
            "Heading changed by {value:.2f} degrees, "
            "exceeding the {threshold:.2f}-degree threshold."
        ),
    )

    add_alerts(
        annotated["flag_extreme_acceleration"],
        anomaly_type="extreme_acceleration",
        severity="high",
        metric_name="acceleration_knots_per_minute",
        metric_values=acceleration,
        threshold=(active_thresholds.acceleration_knots_per_minute),
        description=(
            "Speed changed at {value:.2f} knots per minute, "
            "exceeding the {threshold:.2f} threshold."
        ),
    )

    add_alerts(
        annotated["flag_nonpositive_interval"],
        anomaly_type="nonpositive_interval",
        severity="high",
        metric_name="elapsed_seconds",
        metric_values=elapsed_seconds,
        threshold=0.0,
        description=(
            "Elapsed time was {value:.2f} seconds; "
            "it must be greater than {threshold:.2f}."
        ),
    )

    alerts_dataframe = pd.DataFrame(
        alerts,
        columns=ALERT_COLUMNS,
    )

    return annotated, alerts_dataframe
