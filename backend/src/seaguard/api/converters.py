from seaguard.api.schemas.maritime import PositionResponse
from seaguard.db.models import AISMessage


def position_response(
    message: AISMessage,
) -> PositionResponse:
    """Convert an AIS database model into an API response."""

    return PositionResponse(
        id=message.id,
        timestamp=message.timestamp,
        latitude=message.latitude,
        longitude=message.longitude,
        sog=message.sog,
        cog=message.cog,
        heading=message.heading,
        navigation_status=message.navigation_status,
    )
