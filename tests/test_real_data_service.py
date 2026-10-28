import csv

from backend.services.real_data_service import load_noaa_ais_tracks


def test_load_noaa_ais_tracks_normalizes_noaa_subset(tmp_path):
    path = tmp_path / "noaa_subset.csv"
    rows = [
        {
            "MMSI": "367123456", "BaseDateTime": "2020-01-10T00:26:40Z",
            "LAT": "29.10", "LON": "-94.90", "SOG": "7.2", "COG": "90.0",
            "Heading": "91", "Status": "0", "Draft": "6.5", "IMO": "1234567",
            "VesselName": "TEST TANKER", "CallSign": "TEST1", "VesselType": "82",
            "Length": "210", "Width": "32",
        },
        {
            "MMSI": "367123456", "BaseDateTime": "2020-01-10T00:26:50Z",
            "LAT": "29.11", "LON": "-94.89", "SOG": "7.4", "COG": "91.0",
            "Heading": "92", "Status": "0", "Draft": "6.5", "IMO": "1234567",
            "VesselName": "TEST TANKER", "CallSign": "TEST1", "VesselType": "82",
            "Length": "210", "Width": "32",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    tracks = load_noaa_ais_tracks(str(path))

    assert len(tracks) == 1
    assert tracks[0].metadata.name == "TEST TANKER"
    assert tracks[0].metadata.ship_type == "Crude Oil Tanker"
    assert len(tracks[0].positions) == 2
    assert tracks[0].positions[0].timestamp == "2020-01-10T00:26:40Z"
