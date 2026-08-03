from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import folium
import pandas as pd
from folium.plugins import Fullscreen, MiniMap

REQUIRED_MAP_COLUMNS = {
    "mmsi",
    "timestamp",
    "latitude",
    "longitude",
}


def _normalize_boolean_series(
    values: pd.Series,
) -> pd.Series:
    """Convert Boolean-like CSV values into real Boolean values."""

    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)

    return values.astype("string").str.strip().str.lower().isin({"true", "1", "yes"})


def _display_text(value: Any) -> str:
    """Return escaped text suitable for an HTML popup."""

    if value is None or pd.isna(value):
        return "Not available"

    return escape(str(value))


def _display_number(
    value: Any,
    decimals: int = 2,
) -> str:
    """Format a numeric value for a map popup."""

    if value is None or pd.isna(value):
        return "Not available"

    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return _display_text(value)


def _build_popup_html(
    row: pd.Series,
) -> str:
    """Build the HTML shown when a user clicks a map point."""

    timestamp = row.get("timestamp")

    if pd.notna(timestamp):
        timestamp_text = timestamp.isoformat()
    else:
        timestamp_text = "Not available"

    anomaly_types = row.get("anomaly_types")

    if anomaly_types is None or pd.isna(anomaly_types):
        anomaly_types_text = "None"
    elif str(anomaly_types).strip() == "":
        anomaly_types_text = "None"
    else:
        anomaly_types_text = _display_text(anomaly_types)

    return f"""
    <div style="min-width: 280px;">
        <h4 style="margin-bottom: 8px;">AIS Observation</h4>

        <strong>MMSI:</strong>
        {_display_text(row.get("mmsi"))}
        <br>

        <strong>Timestamp:</strong>
        {_display_text(timestamp_text)}
        <br>

        <strong>Latitude:</strong>
        {_display_number(row.get("latitude"), 6)}
        <br>

        <strong>Longitude:</strong>
        {_display_number(row.get("longitude"), 6)}
        <br>

        <hr>

        <strong>Reported SOG:</strong>
        {_display_number(row.get("sog"))} knots
        <br>

        <strong>Calculated speed:</strong>
        {_display_number(row.get("calculated_speed_knots"))} knots
        <br>

        <strong>COG:</strong>
        {_display_number(row.get("cog"))}°
        <br>

        <strong>Heading:</strong>
        {_display_number(row.get("heading"))}°
        <br>

        <strong>Distance from previous:</strong>
        {_display_number(row.get("distance_nm"))} NM
        <br>

        <strong>Reporting gap:</strong>
        {_display_number(row.get("reporting_gap_minutes"))} minutes
        <br>

        <hr>

        <strong>Has anomaly:</strong>
        {_display_text(row.get("has_anomaly", False))}
        <br>

        <strong>Anomaly count:</strong>
        {_display_text(row.get("anomaly_count", 0))}
        <br>

        <strong>Anomaly types:</strong>
        {anomaly_types_text}
    </div>
    """


def _validate_map_columns(
    dataframe: pd.DataFrame,
) -> None:
    """Ensure that all essential mapping columns exist."""

    missing_columns = REQUIRED_MAP_COLUMNS - set(dataframe.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise ValueError(f"Missing required trajectory map columns: {missing}")


def create_trajectory_map(
    source: pd.DataFrame,
    output_file: Path,
    *,
    maximum_normal_markers: int = 500,
) -> Path:
    """
    Create an interactive map for one vessel trajectory.

    All anomalous observations are displayed. Normal observations are
    sampled when necessary to keep the HTML map reasonably responsive.
    """

    _validate_map_columns(source)

    dataframe = source.copy()

    dataframe["mmsi"] = (
        dataframe["mmsi"].astype("string").str.replace(r"\.0$", "", regex=True)
    )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
        utc=True,
    )

    dataframe["latitude"] = pd.to_numeric(
        dataframe["latitude"],
        errors="coerce",
    )

    dataframe["longitude"] = pd.to_numeric(
        dataframe["longitude"],
        errors="coerce",
    )

    dataframe = dataframe.dropna(
        subset=[
            "mmsi",
            "timestamp",
            "latitude",
            "longitude",
        ]
    )

    dataframe = dataframe.loc[
        dataframe["latitude"].between(-90, 90)
        & dataframe["longitude"].between(-180, 180)
    ].copy()

    if dataframe.empty:
        raise ValueError("No valid geographic observations are available.")

    unique_mmsi_count = dataframe["mmsi"].nunique(dropna=True)

    if unique_mmsi_count != 1:
        raise ValueError(
            f"A trajectory map requires exactly one MMSI. Found {unique_mmsi_count}."
        )

    dataframe = dataframe.sort_values(
        by="timestamp",
        kind="stable",
    ).reset_index(drop=True)

    if "has_anomaly" in dataframe.columns:
        dataframe["has_anomaly"] = _normalize_boolean_series(dataframe["has_anomaly"])
    else:
        dataframe["has_anomaly"] = False

    if "anomaly_count" not in dataframe.columns:
        dataframe["anomaly_count"] = 0

    if "anomaly_types" not in dataframe.columns:
        dataframe["anomaly_types"] = ""

    centre_latitude = float(dataframe["latitude"].median())

    centre_longitude = float(dataframe["longitude"].median())

    vessel_mmsi = str(dataframe.iloc[0]["mmsi"])

    maritime_map = folium.Map(
        location=[
            centre_latitude,
            centre_longitude,
        ],
        zoom_start=12,
        control_scale=True,
        tiles="OpenStreetMap",
    )

    Fullscreen(
        position="topright",
        title="Open full screen",
        title_cancel="Exit full screen",
    ).add_to(maritime_map)

    MiniMap(
        toggle_display=True,
    ).add_to(maritime_map)

    route_layer = folium.FeatureGroup(
        name="Vessel route",
        show=True,
    )

    normal_layer = folium.FeatureGroup(
        name="Normal observations",
        show=False,
    )

    anomaly_layer = folium.FeatureGroup(
        name="Anomalous observations",
        show=True,
    )

    endpoint_layer = folium.FeatureGroup(
        name="Start and end",
        show=True,
    )

    coordinates = list(
        zip(
            dataframe["latitude"],
            dataframe["longitude"],
            strict=True,
        )
    )

    folium.PolyLine(
        locations=coordinates,
        color="#2563eb",
        weight=4,
        opacity=0.8,
        tooltip=(f"Trajectory for MMSI {vessel_mmsi}"),
    ).add_to(route_layer)

    start_row = dataframe.iloc[0]
    end_row = dataframe.iloc[-1]

    folium.CircleMarker(
        location=[
            float(start_row["latitude"]),
            float(start_row["longitude"]),
        ],
        radius=8,
        color="#15803d",
        fill=True,
        fill_color="#22c55e",
        fill_opacity=1.0,
        tooltip="Trajectory start",
        popup=folium.Popup(
            _build_popup_html(start_row),
            max_width=400,
        ),
    ).add_to(endpoint_layer)

    folium.CircleMarker(
        location=[
            float(end_row["latitude"]),
            float(end_row["longitude"]),
        ],
        radius=8,
        color="#7f1d1d",
        fill=True,
        fill_color="#ef4444",
        fill_opacity=1.0,
        tooltip="Trajectory end",
        popup=folium.Popup(
            _build_popup_html(end_row),
            max_width=400,
        ),
    ).add_to(endpoint_layer)

    anomaly_rows = dataframe.loc[dataframe["has_anomaly"]]

    normal_rows = dataframe.loc[~dataframe["has_anomaly"]]

    if maximum_normal_markers > 0 and len(normal_rows) > maximum_normal_markers:
        step = max(
            1,
            len(normal_rows) // maximum_normal_markers,
        )

        normal_rows = normal_rows.iloc[::step].head(maximum_normal_markers)

    for _, row in normal_rows.iterrows():
        folium.CircleMarker(
            location=[
                float(row["latitude"]),
                float(row["longitude"]),
            ],
            radius=3,
            color="#1d4ed8",
            weight=1,
            fill=True,
            fill_color="#60a5fa",
            fill_opacity=0.7,
            tooltip=(f"{row['timestamp']} — normal observation"),
            popup=folium.Popup(
                _build_popup_html(row),
                max_width=400,
            ),
        ).add_to(normal_layer)

    for _, row in anomaly_rows.iterrows():
        anomaly_text = row.get(
            "anomaly_types",
            "anomaly",
        )

        folium.CircleMarker(
            location=[
                float(row["latitude"]),
                float(row["longitude"]),
            ],
            radius=7,
            color="#7f1d1d",
            weight=2,
            fill=True,
            fill_color="#dc2626",
            fill_opacity=0.9,
            tooltip=(f"{row['timestamp']} — {anomaly_text}"),
            popup=folium.Popup(
                _build_popup_html(row),
                max_width=400,
            ),
        ).add_to(anomaly_layer)

    route_layer.add_to(maritime_map)
    normal_layer.add_to(maritime_map)
    anomaly_layer.add_to(maritime_map)
    endpoint_layer.add_to(maritime_map)

    folium.LayerControl(
        collapsed=False,
    ).add_to(maritime_map)

    minimum_latitude = float(dataframe["latitude"].min())

    maximum_latitude = float(dataframe["latitude"].max())

    minimum_longitude = float(dataframe["longitude"].min())

    maximum_longitude = float(dataframe["longitude"].max())

    maritime_map.fit_bounds(
        [
            [
                minimum_latitude,
                minimum_longitude,
            ],
            [
                maximum_latitude,
                maximum_longitude,
            ],
        ],
        padding=(30, 30),
    )

    output_file = output_file.resolve()

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    maritime_map.save(str(output_file))

    return output_file
