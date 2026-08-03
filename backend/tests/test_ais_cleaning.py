import pandas as pd

from seaguard.ais.cleaning import clean_ais_dataframe


def test_clean_ais_dataframe() -> None:
    """AIS cleaning should validate, reject, and deduplicate rows."""

    source = pd.DataFrame(
        [
            {
                "MMSI": "123456789",
                "BaseDateTime": "2024-06-15T00:00:00",
                "LAT": 36.90,
                "LON": -76.30,
                "SOG": 5.0,
                "COG": 10.0,
                "Heading": 11,
            },
            {
                "MMSI": "987654321",
                "BaseDateTime": "2024-06-15T00:01:00",
                "LAT": 36.91,
                "LON": -76.31,
                "SOG": 102.3,
                "COG": 360.0,
                "Heading": 511,
            },
            {
                "MMSI": "111111111",
                "BaseDateTime": "not-a-date",
                "LAT": 100.0,
                "LON": -76.20,
                "SOG": -1.0,
                "COG": 500.0,
                "Heading": 400,
            },
            {
                "MMSI": "123456789",
                "BaseDateTime": "2024-06-15T00:00:00",
                "LAT": 36.90,
                "LON": -76.30,
                "SOG": 5.0,
                "COG": 10.0,
                "Heading": 11,
            },
        ]
    )

    cleaned, rejected, report = clean_ais_dataframe(source)

    assert len(cleaned) == 2
    assert len(rejected) == 1

    assert report["rows_read"] == 4
    assert report["rows_clean"] == 2
    assert report["rows_rejected"] == 1
    assert report["duplicates_removed"] == 1

    unavailable_row = cleaned.loc[cleaned["mmsi"] == "987654321"].iloc[0]

    assert pd.isna(unavailable_row["sog"])
    assert pd.isna(unavailable_row["cog"])
    assert pd.isna(unavailable_row["heading"])

    assert bool(unavailable_row["sog_unavailable"])
    assert bool(unavailable_row["cog_unavailable"])
    assert bool(unavailable_row["heading_unavailable"])


def test_missing_required_columns_raise_error() -> None:
    """Cleaning should fail clearly if core AIS columns are absent."""

    source = pd.DataFrame(
        {
            "MMSI": ["123456789"],
            "LAT": [36.90],
        }
    )

    try:
        clean_ais_dataframe(source)
    except ValueError as error:
        message = str(error)

        assert "timestamp" in message
        assert "longitude" in message
    else:
        raise AssertionError("Expected clean_ais_dataframe to raise ValueError.")
