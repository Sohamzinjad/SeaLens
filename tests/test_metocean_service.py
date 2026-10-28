from pathlib import Path

import numpy as np

from backend.services.metocean_service import RealMetOceanGridEngine


def test_cached_grids_are_bilinear_and_time_interpolated(tmp_path: Path):
    engine = RealMetOceanGridEngine(tmp_path)
    incident = tmp_path / "test-incident"
    incident.mkdir()

    # Two adjacent hourly GFS grids. At 01:15 UTC the expected u component is 3.
    for timestamp, u_value in ((3600.0, 2.0), (7200.0, 6.0)):
        np.savez_compressed(
            incident / f"gfs_wind_{int(timestamp)}.npz",
            lat=np.array([0.0, 1.0]), lon=np.array([0.0, 1.0]), time=np.array([timestamp]),
            u=np.full((1, 2, 2), u_value), v=np.zeros((1, 2, 2)),
        )
    # At the centre, the spatial bilinear value is 4; halfway in time it is 5.
    np.savez_compressed(
        incident / "copernicus_surface_currents.npz",
        lat=np.array([0.0, 1.0]), lon=np.array([0.0, 1.0]), time=np.array([3600.0, 7200.0]),
        u=np.array([[[1.0, 3.0], [5.0, 7.0]], [[3.0, 5.0], [7.0, 9.0]]]),
        v=np.zeros((2, 2, 2)),
    )
    engine._incident_dir = incident

    assert engine._find_sample("gfs_wind_", 0.5, 0.5, 4500.0) == (3.0, 0.0)
    assert engine._find_sample("copernicus_surface_currents", 0.5, 0.5, 5400.0) == (5.0, 0.0)
    result = engine.get_interpolated_vectors(0.5, 0.5, 1.25, 8.0, 90.0, 0.2, 90.0)
    assert result["wind_source"] == "NOAA GFS cached grid"
    assert result["current_source"] == "Copernicus Marine cached grid"
    assert result["modelled_fallback"] is False
