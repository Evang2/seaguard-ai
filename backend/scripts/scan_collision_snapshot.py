import argparse
import json
from math import isfinite
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from seaguard.collision import (
    EncounterVessel,
    evaluate_collision_encounters,
)

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_POSITION_LIMIT = 500

#
# Twenty nautical miles is deliberately larger than the
# geographic radius we used in the simple candidate tests.
#
# Our collision classifier considers encounters up to
# 45 minutes into the future. A 5 NM search radius could
# therefore miss fast-closing encounters before they enter
# that smaller radius.
#
DEFAULT_MAX_DISTANCE_NM = 20.0


def fetch_recent_positions(
    *,
    api_base_url: str,
    limit: int,
) -> list[dict[str, object]]:
    """Fetch the current SeaGuard vessel snapshot."""

    query = urlencode(
        {
            "limit": limit,
        }
    )

    url = f"{api_base_url.rstrip('/')}/api/v1/positions/recent?{query}"

    try:
        with urlopen(
            url,
            timeout=10.0,
        ) as response:
            payload = json.load(response)

    except HTTPError as error:
        raise RuntimeError(
            "SeaGuard API returned "
            f"HTTP {error.code} while loading "
            "recent vessel positions."
        ) from error

    except URLError as error:
        raise RuntimeError(
            "Could not connect to the SeaGuard API. "
            "Make sure FastAPI is running on "
            f"{api_base_url}."
        ) from error

    if not isinstance(payload, dict):
        raise RuntimeError("Recent-position API returned an unexpected response.")

    items = payload.get("items")

    if not isinstance(items, list):
        raise RuntimeError(
            "Recent-position API response does not contain an 'items' list."
        )

    return items


def _number_or_none(
    value: object,
) -> float | None:
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(number):
        return None

    return number


def build_encounter_vessels(
    positions: list[dict[str, object]],
) -> tuple[
    tuple[EncounterVessel, ...],
    int,
]:
    """
    Convert API position records into collision-engine states.

    AIS records without usable SOG or COG cannot participate
    in a constant-velocity CPA/TCPA calculation, so they are
    skipped and reported separately.
    """

    vessels_by_mmsi: dict[
        str,
        EncounterVessel,
    ] = {}

    skipped_count = 0

    for position in positions:
        mmsi_value = position.get("mmsi")

        if not isinstance(
            mmsi_value,
            str,
        ):
            skipped_count += 1
            continue

        mmsi = mmsi_value.strip()

        latitude = _number_or_none(position.get("latitude"))

        longitude = _number_or_none(position.get("longitude"))

        sog_knots = _number_or_none(position.get("sog"))

        cog_degrees = _number_or_none(position.get("cog"))

        if (
            not mmsi
            or latitude is None
            or longitude is None
            or sog_knots is None
            or cog_degrees is None
        ):
            skipped_count += 1
            continue

        if not -90.0 <= latitude <= 90.0:
            skipped_count += 1
            continue

        if not -180.0 <= longitude <= 180.0:
            skipped_count += 1
            continue

        if sog_knots < 0.0:
            skipped_count += 1
            continue

        vessels_by_mmsi[mmsi] = EncounterVessel(
            mmsi=mmsi,
            latitude=latitude,
            longitude=longitude,
            sog_knots=sog_knots,
            cog_degrees=cog_degrees,
        )

    vessels = tuple(
        sorted(
            vessels_by_mmsi.values(),
            key=lambda vessel: vessel.mmsi,
        )
    )

    return (
        vessels,
        skipped_count,
    )


def format_tcpa(
    tcpa_minutes: float | None,
) -> str:
    if tcpa_minutes is None:
        return "N/A"

    return f"{tcpa_minutes:.2f} min"


def print_scan_report(
    *,
    source_position_count: int,
    usable_vessel_count: int,
    skipped_position_count: int,
    max_distance_nm: float,
    scan,
    top: int,
) -> None:
    """Print a readable collision-scan report."""

    candidate_search = scan.candidate_search

    print()
    print("=" * 72)
    print("SeaGuard AI — Collision Encounter Scan")
    print("=" * 72)

    print()
    print("Snapshot")
    print(f"  API position records:      {source_position_count:,}")
    print(f"  Usable motion states:      {usable_vessel_count:,}")
    print(f"  Skipped records:           {skipped_position_count:,}")
    print(f"  Search radius:             {max_distance_nm:.1f} NM")

    print()
    print("Candidate filtering")
    print(f"  Theoretical vessel pairs:  {candidate_search.possible_pair_count:,}")
    print(
        f"  Distance checks performed: {candidate_search.distance_checked_pair_count:,}"
    )
    print(f"  Nearby candidates:         {candidate_search.candidate_count:,}")
    print(f"  CPA/TCPA assessments:      {scan.assessed_candidate_count:,}")

    print()
    print("Collision classification")
    print(f"  CRITICAL:                  {scan.critical_count:,}")
    print(f"  HIGH:                      {scan.high_count:,}")
    print(f"  MEDIUM:                    {scan.medium_count:,}")
    print(f"  LOW:                       {scan.low_count:,}")

    elevated_encounters = [
        encounter
        for encounter in scan.encounters
        if (encounter.risk.risk_level != "low")
    ]

    print()
    print(f"Elevated encounters: {len(elevated_encounters):,}")

    if not elevated_encounters:
        print()
        print(
            "No MEDIUM, HIGH, or CRITICAL "
            "collision encounters were found "
            "in this snapshot."
        )
        print()
        print("This is a valid result; it does not mean the collision engine failed.")
        return

    print()

    for (
        index,
        encounter,
    ) in enumerate(
        elevated_encounters[:top],
        start=1,
    ):
        risk = encounter.risk

        print("-" * 72)

        print(f"#{index} {risk.risk_level.upper()}")

        print(f"  Vessel A:        {encounter.vessel_a.mmsi}")

        print(f"  Vessel B:        {encounter.vessel_b.mmsi}")

        print(f"  Current distance: {risk.current_distance_nm:.3f} NM")

        print(f"  Future CPA:      {risk.cpa_distance_nm:.3f} NM")

        print(f"  TCPA:            {format_tcpa(risk.tcpa_minutes)}")

        print(f"  Relative speed:  {risk.relative_speed_knots:.2f} kn")

        print(f"  Closing speed:   {risk.closing_speed_knots:.2f} kn")

        print(f"  Bearing A → B:   {encounter.cpa.bearing_from_a_to_b_degrees:.1f}°")

        print("  Reasons:")

        for reason in risk.reasons:
            print(f"    - {reason}")

    if len(elevated_encounters) > top:
        remaining = len(elevated_encounters) - top

        print()
        print(f"... {remaining:,} additional elevated encounters not displayed.")

    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run SeaGuard CPA/TCPA collision analysis "
            "against the current API vessel snapshot."
        )
    )

    parser.add_argument(
        "--api-base-url",
        default=(DEFAULT_API_BASE_URL),
        help=("SeaGuard FastAPI base URL."),
    )

    parser.add_argument(
        "--position-limit",
        type=int,
        default=(DEFAULT_POSITION_LIMIT),
        help=("Maximum number of recent vessel positions requested from the API."),
    )

    parser.add_argument(
        "--max-distance-nm",
        type=float,
        default=(DEFAULT_MAX_DISTANCE_NM),
        help=("Maximum current vessel separation for encounter candidate evaluation."),
    )

    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help=("Maximum number of elevated encounters to print."),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.position_limit <= 0:
        raise ValueError("Position limit must be positive.")

    if args.top <= 0:
        raise ValueError("Top encounter count must be positive.")

    positions = fetch_recent_positions(
        api_base_url=(args.api_base_url),
        limit=(args.position_limit),
    )

    (
        vessels,
        skipped_count,
    ) = build_encounter_vessels(
        positions,
    )

    scan = evaluate_collision_encounters(
        vessels,
        max_distance_nm=(args.max_distance_nm),
        include_low=True,
    )

    print_scan_report(
        source_position_count=(len(positions)),
        usable_vessel_count=(len(vessels)),
        skipped_position_count=(skipped_count),
        max_distance_nm=(args.max_distance_nm),
        scan=scan,
        top=args.top,
    )


if __name__ == "__main__":
    main()
