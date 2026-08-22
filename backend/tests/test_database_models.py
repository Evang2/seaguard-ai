from geoalchemy2 import Geography

from seaguard.db import models  # noqa: F401
from seaguard.db.base import Base
from seaguard.db.risk_models import RiskAssessment


def test_expected_tables_are_registered() -> None:
    """All core maritime tables should be registered."""

    expected_tables = {
        "vessels",
        "ais_messages",
        "anomaly_alerts",
        "import_jobs",
        "risk_assessments",
    }
    assert RiskAssessment.__tablename__ == "risk_assessments"
    assert expected_tables == set(Base.metadata.tables)


def test_ais_position_is_geographic_point() -> None:
    """AIS messages should use a WGS 84 geography point."""

    table = Base.metadata.tables["ais_messages"]
    position_type = table.c.position.type

    assert isinstance(position_type, Geography)
    assert position_type.geometry_type == "POINT"
    assert position_type.srid == 4326


def test_vessel_mmsi_is_unique() -> None:
    """The database should prevent duplicate vessel MMSIs."""

    table = Base.metadata.tables["vessels"]

    assert table.c.mmsi.unique is True
    assert table.c.mmsi.nullable is False
