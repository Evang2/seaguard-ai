from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, isfinite, radians, sin

NAUTICAL_MILES_PER_LATITUDE_DEGREE = 60.0
RELATIVE_SPEED_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class VesselMotion:
    """Single vessel motion state used for encounter calculations."""

    latitude: float
    longitude: float
    sog_knots: float
    cog_degrees: float


@dataclass(frozen=True, slots=True)
class CPAResult:
    """Relative-motion result for two vessels."""

    current_distance_nm: float
    relative_speed_knots: float
    closing_speed_knots: float

    bearing_from_a_to_b_degrees: float

    tcpa_minutes: float | None
    cpa_distance_nm: float
    future_cpa_distance_nm: float

    is_closing: bool


def _validate_motion(
    motion: VesselMotion,
) -> None:
    values = (
        motion.latitude,
        motion.longitude,
        motion.sog_knots,
        motion.cog_degrees,
    )

    if not all(isfinite(value) for value in values):
        raise ValueError("Vessel motion values must be finite numbers.")

    if not -90.0 <= motion.latitude <= 90.0:
        raise ValueError("Latitude must be between -90 and 90 degrees.")

    if not -180.0 <= motion.longitude <= 180.0:
        raise ValueError("Longitude must be between -180 and 180 degrees.")

    if motion.sog_knots < 0.0:
        raise ValueError("Speed over ground cannot be negative.")


def _normalize_longitude_difference(
    longitude_difference: float,
) -> float:
    """Return the shortest signed longitude difference."""

    return (longitude_difference + 180.0) % 360.0 - 180.0


def _relative_position_nm(
    vessel_a: VesselMotion,
    vessel_b: VesselMotion,
) -> tuple[float, float]:
    """
    Return B relative to A in a local east/north plane.

    The approximation uses 60 nautical miles per latitude degree
    and scales longitude by the cosine of the mean latitude.

    It is intended for local vessel-encounter calculations rather
    than long-distance ocean routing.
    """

    latitude_difference = vessel_b.latitude - vessel_a.latitude

    longitude_difference = _normalize_longitude_difference(
        vessel_b.longitude - vessel_a.longitude
    )

    mean_latitude_radians = radians((vessel_a.latitude + vessel_b.latitude) / 2.0)

    north_nm = latitude_difference * NAUTICAL_MILES_PER_LATITUDE_DEGREE

    east_nm = (
        longitude_difference
        * NAUTICAL_MILES_PER_LATITUDE_DEGREE
        * cos(mean_latitude_radians)
    )

    return east_nm, north_nm


def _velocity_components_knots(
    motion: VesselMotion,
) -> tuple[float, float]:
    """
    Convert maritime COG/SOG into east/north velocity.

    Maritime convention:
    - 0 degrees = north
    - 90 degrees = east
    - 180 degrees = south
    - 270 degrees = west
    """

    course_radians = radians(motion.cog_degrees % 360.0)

    east_knots = motion.sog_knots * sin(course_radians)

    north_knots = motion.sog_knots * cos(course_radians)

    return (
        east_knots,
        north_knots,
    )


def _bearing_degrees(
    east_nm: float,
    north_nm: float,
) -> float:
    """Return maritime bearing from the local east/north vector."""

    if abs(east_nm) < RELATIVE_SPEED_EPSILON and abs(north_nm) < RELATIVE_SPEED_EPSILON:
        return 0.0

    return (
        degrees(
            atan2(
                east_nm,
                north_nm,
            )
        )
        + 360.0
    ) % 360.0


def calculate_cpa_tcpa(
    vessel_a: VesselMotion,
    vessel_b: VesselMotion,
) -> CPAResult:
    """
    Calculate CPA and TCPA using constant-velocity relative motion.

    CPA:
        Closest Point of Approach distance.

    TCPA:
        Time until the mathematical closest point of approach.

    A negative TCPA means the mathematical closest approach
    already occurred.

    `future_cpa_distance_nm` is therefore provided separately.
    For a negative TCPA it is the current separation rather than
    the historical CPA distance.
    """

    _validate_motion(vessel_a)
    _validate_motion(vessel_b)

    (
        relative_east_nm,
        relative_north_nm,
    ) = _relative_position_nm(
        vessel_a,
        vessel_b,
    )

    current_distance_nm = hypot(
        relative_east_nm,
        relative_north_nm,
    )

    (
        vessel_a_east_knots,
        vessel_a_north_knots,
    ) = _velocity_components_knots(
        vessel_a,
    )

    (
        vessel_b_east_knots,
        vessel_b_north_knots,
    ) = _velocity_components_knots(
        vessel_b,
    )

    relative_east_knots = vessel_b_east_knots - vessel_a_east_knots

    relative_north_knots = vessel_b_north_knots - vessel_a_north_knots

    relative_speed_knots = hypot(
        relative_east_knots,
        relative_north_knots,
    )

    relative_dot_product = (
        relative_east_nm * relative_east_knots
        + relative_north_nm * relative_north_knots
    )

    if current_distance_nm <= RELATIVE_SPEED_EPSILON:
        closing_speed_knots = 0.0
    else:
        closing_speed_knots = -relative_dot_product / current_distance_nm

    bearing_degrees = _bearing_degrees(
        relative_east_nm,
        relative_north_nm,
    )

    if relative_speed_knots <= RELATIVE_SPEED_EPSILON:
        return CPAResult(
            current_distance_nm=current_distance_nm,
            relative_speed_knots=0.0,
            closing_speed_knots=0.0,
            bearing_from_a_to_b_degrees=(bearing_degrees),
            tcpa_minutes=None,
            cpa_distance_nm=current_distance_nm,
            future_cpa_distance_nm=(current_distance_nm),
            is_closing=False,
        )

    relative_speed_squared = relative_east_knots**2 + relative_north_knots**2

    tcpa_hours = -relative_dot_product / relative_speed_squared

    tcpa_minutes = tcpa_hours * 60.0

    closest_east_nm = relative_east_nm + relative_east_knots * tcpa_hours

    closest_north_nm = relative_north_nm + relative_north_knots * tcpa_hours

    cpa_distance_nm = hypot(
        closest_east_nm,
        closest_north_nm,
    )

    if tcpa_hours > 0.0:
        future_cpa_distance_nm = cpa_distance_nm
    else:
        future_cpa_distance_nm = current_distance_nm

    is_closing = closing_speed_knots > 0.0 and tcpa_hours > 0.0

    return CPAResult(
        current_distance_nm=(current_distance_nm),
        relative_speed_knots=(relative_speed_knots),
        closing_speed_knots=(closing_speed_knots),
        bearing_from_a_to_b_degrees=(bearing_degrees),
        tcpa_minutes=tcpa_minutes,
        cpa_distance_nm=cpa_distance_nm,
        future_cpa_distance_nm=(future_cpa_distance_nm),
        is_closing=is_closing,
    )
