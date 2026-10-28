# Architecture & Workflow

**SAR detection → ocean/wind backtrack → AIS correlation → uncertainty-aware dossier**

## Pipeline
1. **SAR Detection** (`ml_engine/`) – Sentinel-1 SAR ingestion, Lee speckle filter, U-Net segmentation / CFAR ship detection, look-alike rejection. Produces slick polygons with confidence/volume estimates.
2. **Ocean/Wind Backtrack** (`backend/services/drift_engine.py`, `metocean_service.py`) – Reverse Lagrangian drift with Leeway/coriolis, 15-min dynamic steps, uncertainty cone/ellipse growing with time. Supports GFS wind / Copernicus currents with provenance tracking and modelled fallback.
3. **AIS Correlation** (`backend/services/correlation_engine.py`, `dark_vessel_engine.py`, `real_data_service.py`) – Spatio-temporal matching to AIS tracks, dark vessel detection, behavioral anomalies, repeat offender scoring.
4. **Uncertainty-Aware Dossier** (`backend/services/report_generator.py`, `intelligence_brief_generator.py`) – Forensic dossier with data sources, timestamps, cache status, uncertainty warnings, cryptographic hash.

## Sources & Badges
- Sentinel-1, NOAA AIS, NOAA GFS, Copernicus, or modelled fallback (clearly labeled)
