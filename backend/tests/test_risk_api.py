from seaguard.api.schemas.risk import (
    RiskAssessmentListResponse,
    RiskAssessmentResponse,
)
from seaguard.main import app


def _route_paths() -> set[str]:
    return set(app.openapi()["paths"])


def test_risk_routes_are_registered() -> None:
    paths = _route_paths()

    assert "/api/v1/risk" in paths
    assert "/api/v1/risk/{mmsi}" in paths


def test_risk_list_documents_expected_filters() -> None:
    openapi = app.openapi()

    parameters = {
        parameter["name"]
        for parameter in openapi["paths"]["/api/v1/risk"]["get"]["parameters"]
    }

    assert {
        "mmsi",
        "risk_level",
        "minimum_ml_percentile",
        "detector_agreement",
        "start_time",
        "end_time",
        "limit",
        "offset",
    }.issubset(parameters)


def test_risk_response_schema_validates_assessment() -> None:
    item = RiskAssessmentResponse.model_validate(
        {
            "id": 1,
            "ais_message_id": 42,
            "mmsi": "367784640",
            "observed_at": ("2024-06-14T13:05:28Z"),
            "latitude": 40.71,
            "longitude": -74.01,
            "ml_anomaly_score": 0.253998,
            "ml_anomaly_percentile": 99.98,
            "rule_flag_count": 3,
            "rule_severity": "high",
            "detector_agreement": True,
            "risk_level": "critical",
            "risk_reasons": ("rules=speed_mismatch; ml_percentile=99.98"),
            "assessment_version": "hybrid-v1",
        }
    )

    response = RiskAssessmentListResponse(
        items=[item],
        total=1,
        limit=100,
        offset=0,
    )

    assert response.total == 1
    assert response.items[0].risk_level == "critical"
    assert response.items[0].ml_anomaly_percentile == 99.98
