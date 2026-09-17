# seaLens: SAR Oil Spill Detection & AIS Vessel Correlation System
**SIH Problem #143 (NTRO)**

## System Overview
**seaLens** is an AI-powered maritime environmental defense and forensic intelligence system. It pairs Synthetic Aperture Radar (SAR) satellite Earth Observation with global Automatic Identification System (AIS) vessel telemetry to detect illegal oil discharges at sea, reverse-simulate ocean drift, and correlate culprit vessels with forensic certainty.

### Key Capabilities
1. **SAR Oil Slick Segmentation Engine**: Uses polarimetric SAR features (VV/VH ratio, speckle suppression, entropy) + deep convolutional segmentation (U-Net / SegFormer) to delineate slick contours and calculate spill volume/area.
2. **False Positive & Look-Alike Rejection**: Employs oceanographic context (wind speed from ECMWF/ERA5, biogenic film characteristics) to weed out natural low-wind calm water and algae blooms.
3. **Reverse Lagrangian Drift Physics**: Back-projects the slick's movement using vector fields of ocean surface currents and wind leeway ($3\%$ rule) to establish the spatio-temporal origin cone $(X_0, Y_0, T_0)$.
4. **PostGIS Spatio-Temporal Trajectory Correlation**: Intersects the origin cone against AIS vessel tracks, evaluating Closest Point of Approach (CPA), speed anomalies, and vessel risk priors.
5. **Interactive C2 Dashboard & Evidence Dossier**: Real-time map with timeline scrubber, vessel telemetry drilldowns, and 1-click legal PDF evidence reports.

### Recent Updates
- **Frontend / UI**: Upgraded the C2 dashboard with light-themed, draggable popup bezels, click-to-open previews, and thickened glass frame padding for SAR images.
- **Backend Services**: Introduced the `CoastalWaterEngine` for coastal water modeling and updated the `LandfallPredictor`.
- **Data & Reporting**: Enhanced scenario data definitions, report generation capabilities, and updated sample SAR scene TIFF data files.
- **Testing**: Updated SAR CV pipeline tests and the innovation test suite.

---

## 📋 System Audit & Future Scope
For a detailed breakdown of what the current prototype has vs. what it lacks for production deployment, see **[LIMITATIONS_AND_ROADMAP.md](LIMITATIONS_AND_ROADMAP.md)**.

### Quick Gap Summary:
* **CV/ML**: High-level geometric/feature segmentation is implemented; needs pretrained PyTorch `.pt` weights for raw 16-bit GeoTIFF inference.
* **Radar Ship Detection**: AIS correlation is active; needs CFAR/YOLO ship detection to catch "Dark Vessels" that turn off AIS.
* **Physics**: 2D constant Lagrangian backtrack is active; dynamic CMEMS/GFS gridded fields & forward landfall ETA are planned for Phase 2.
* **Database**: In-memory spatial index with Haversine math is active; full PostGIS cluster is planned for production scale.

---

## 🚀 Quickstart
```bash
# 1. Activate dedicated environment
source venv/bin/activate

# 2. Run test suite
python3 -m pytest tests/test_pipeline.py -v   # or run PYTHONPATH=. python3 tests/test_pipeline.py

# 3. Launch Operations Command Center
python3 start.py
```
Open **`http://localhost:8000`** in your browser.
