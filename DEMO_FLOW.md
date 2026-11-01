# Rehearsed Demo Flow

1. **Choose Case** – Start at `/c2`, select scenario (e.g., Wakashio validation) or use Real Data Mode. Banner clearly shows Demo/Historical/Live status.
2. **Run SAR** – Use "Run Public Sentinel-1 RTC Case" or GeoTIFF + CFAR pipeline. View SAR overlays and confidence.
3. **Import AIS** – Use "Import Matched NOAA AIS Window" (or view existing vessel tracks). NOAA AIS results appear on map and vessel panel.
4. **Backtrack** – Use "Run GFS Wind Backtracking" / drift simulation. View backtracked origin, uncertainty cone, provenance badges (Sentinel-1/NOAA AIS/NOAA GFS/Copernicus/modelled fallback).
5. **Show Ranked Vessel Leads** – Review culprit list with scores, behavioral anomalies, dark vessels, repeat offenders.
6. **Generate Dossier** – Click "Generate Forensic Dossier", review sources/timestamps/cache/uncertainty, export PDF/Markdown.

**Fallbacks:** If internet fails, use the clearly labelled simulated scenarios. A real-data offline package is not shipped until it can be built with verified source provenance.
