import argparse

from seaguard.collision.persistence import (
    DEFAULT_MAX_DISTANCE_NM,
    DEFAULT_MAX_PAIR_TIME_GAP_MINUTES,
    persist_collision_snapshot,
)
from seaguard.db.session import SessionFactory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the latest AIS vessel states, "
            "detect elevated CPA/TCPA collision encounters, "
            "and persist them to the database."
        )
    )

    parser.add_argument(
        "--max-distance-nm",
        type=float,
        default=DEFAULT_MAX_DISTANCE_NM,
        help=("Maximum vessel separation used during candidate generation."),
    )

    parser.add_argument(
        "--max-pair-time-gap-minutes",
        type=float,
        default=DEFAULT_MAX_PAIR_TIME_GAP_MINUTES,
        help=(
            "Maximum allowed timestamp difference between "
            "the two source AIS observations."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with SessionFactory() as session:
        result = persist_collision_snapshot(
            session,
            max_distance_nm=args.max_distance_nm,
            max_pair_time_gap_minutes=(args.max_pair_time_gap_minutes),
        )

    print()
    print("SeaGuard AI — Persist Collision Snapshot")
    print()

    print("AIS snapshot")
    print(f"  Latest vessel positions: {result.latest_position_count}")
    print(f"  Usable vessel states: {result.usable_vessel_count}")
    print(f"  Unusable latest states: {result.skipped_unusable_count}")

    print()
    print("Candidate generation")
    print(f"  Theoretical pairs: {result.possible_pair_count}")
    print(f"  Nearby candidates: {result.candidate_count}")
    print(f"  CPA/TCPA assessments: {result.assessed_candidate_count}")

    print()
    print("Elevated encounters")
    print(f"  Detected: {result.elevated_encounter_count}")
    print(f"  Time-aligned: {result.eligible_encounter_count}")
    print(f"  Skipped for time gap: {result.skipped_time_gap_count}")

    print()
    print("Persistence")
    print(f"  Inserted: {result.inserted_count}")
    print(f"  Already persisted: {result.duplicate_count}")
    print()


if __name__ == "__main__":
    main()
