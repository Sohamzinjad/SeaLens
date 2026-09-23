# seaLens: Current System Limitations & Engineering Gap Analysis
**SIH Problem #143 (NTRO): Oil Spill Detection via Satellite SAR & AIS Vessel Correlation**

This document provides a technical audit of the current prototype, identifying what the system currently has, what it **lacks**, and the engineering roadmap required for a full enterprise/defense-grade deployment.

---

## Executive Summary Matrix

| Capability Area | Current Prototype State | Enterprise / Defense Target | Gap Severity |
| :--- | :--- | :--- | :---: |
| **SAR AI Model** | 🟡 U-Net weights and tiled raster inference run only in `POST /api/process_synthetic_geotiff`; the three interactive scenarios use pre-authored vector slick specifications | Scaled multi-GPU distributed inference across Sentinel-1 archives | 🟡 Medium |
| **Raw SAR Ingestion** | ✅ `rasterio` 16-bit GeoTIFF decoding, 5x5 Lee filter, and WGS84 vectorization run in `POST /api/process_synthetic_geotiff` | Direct ESA Copernicus Hub S1 `.SAFE` auto-downloader | 🟢 Resolved (prototype path) |
| **Dark Vessel Detection** | ✅ Each scenario builds/caches a synthetic SAR raster with embedded pixel echoes, runs CA-CFAR, then cross-matches those detections with AIS | Multi-spectral infrared & optical satellite constellation fusion | 🟢 Resolved (synthetic-demo path) |
| **Reverse Drift / Attribution** | ✅ `DriftEngine.backtrack_origin()` traces each scenario backward in 15-minute steps through modeled dynamic vectors; `backtrack_origin_simple()` remains an explicit constant-vector fallback | Dynamic path-wise CMEMS/GFS fields for attribution | 🟢 Resolved (modeled-grid path) |
| **Forward Drift / Landfall** | ✅ `CoastalLandfallPredictor` uses `DynamicOceanGridEngine` at each hourly step in `GET /api/forward_drift/{scenario_id}` | Automated Coast Guard satellite SMS alerting dispatch | 🟢 Resolved (prototype path) |
| **Oil Weathering** | ✅ Simplified evaporation, emulsification, and Fay-spreading curve runs in `GET /api/weathering_simulation/{scenario_id}` and the forward forecast | Multi-fraction distillation curve chemical laboratory validation | 🟢 Resolved (prototype path) |
| **AIS Ingestion & DB** | In-memory spatial scenarios & Python Haversine math | PostgreSQL + PostGIS with GIST indexing & live AISStream WebSockets | 🟡 Medium |
| **UI Custom Input** | ✅ 3 Scenarios + "Run GeoTIFF + CFAR" + "72h Landfall & Weathering" in UI | Drag-and-drop satellite image upload & custom AIS file ingestion | 🟡 Medium |
| **Dossier Export** | Markdown rendering with browser print | Direct binary PDF export with embedded maps & SHA-256 seal | 🟡 Medium |
| **Deployment** | Python virtual environment with PyTorch & Rasterio | Dockerized multi-container stack (`docker-compose.yml`) | 🟢 Low |

---

## 1. Computer Vision & Earth Observation Gaps

### 1.1 Scenario Pipeline Does Not Use Raw-Raster U-Net Inference
* **Current State**: A trained PyTorch U-Net checkpoint is loaded at startup and performs tiled inference on normalized GeoTIFF pixels in `POST /api/process_synthetic_geotiff`. The three interactive scenarios, however, create slick geometry from authored feature specifications through `SAROilSpillDetector.process_sar_scene()`.
* **What It Lacks**: The primary scenario/demo path does not execute the U-Net on a scenario raster.
* **Engineering Solution**:
  * Integrate a pretrained PyTorch `U-Net` / `SegFormer-B2` checkpoint trained on the **Deep-SAR** or **Marine Oil Spill Dataset** (e.g., Keras/PyTorch `.pt` or `.onnx` models).
  * Load model weights during startup to generate pixel probability masks from grayscale SAR crops.

### 1.2 Raw GeoTIFF Ingestion Scope (`.SAFE` / `.tif`)
* **Current State**: `GeoTIFFProcessor` decodes local 16-bit GeoTIFFs with `rasterio`, normalizes them, filters speckle, and vectorizes masks in the synthetic-GeoTIFF endpoint.
* **What It Lacks**: It does not ingest multi-gigabyte Sentinel-1 Level-1 GRD `.SAFE` zip archives or download source data directly from ESA Copernicus Open Access Hub.
* **Engineering Solution**:
  * Add `rasterio` and `GDAL` pipelines to read GeoTIFF rasters.
  * Apply radiometric calibration: $\sigma^0 = 10 \cdot \log_{10}(DN^2) - K_{\text{cal}}$.
  * Apply a **Lee or Frost speckle suppression filter** ($5 \times 5$ window) to reduce radar granular noise.

### 1.3 Independent SAR Ship Spotting ("Dark Vessel" Detection)
* **Current State**: `GET /api/dark_vessels/{scenario_id}` creates or reuses a scenario GeoTIFF containing embedded ship-like pixel scatterers, runs `CACFARShipDetector`, and sends its output to `DarkVesselEngine` for AIS cross-matching. The scenario raster is synthetic, but detections are derived from pixels rather than a precomputed radar-target list.
* **What It Lacks**: The prototype does not yet use real satellite scenes, multi-spectral corroboration, or a production vessel-classification model.
* **Engineering Solution**:
  * Implement a **Constant False Alarm Rate (CFAR)** detector or a lightweight YOLOv8-OBB (Oriented Bounding Box) ship detector to identify bright point scatterers (metallic ships) in SAR.
  * Perform a **Spatial Difference Join**: If SAR detects a physical ship at $(Lat, Lng)$ with *no matching AIS broadcast* within a 5-mile radius, flag as a **"Dark Vessel Alert"**.

---

## 2. Oceanographic & Drift Physics Gaps

### 2.1 Dynamic Modeled Weather Fields vs. Live Observations
* **Current State**: Reverse attribution uses `DynamicOceanGridEngine` at the particle's changing position and prior time in 15-minute steps. The forward forecast queries the same modeled grid hourly, using M2 tidal oscillation, diurnal wind variation, and a spatial wind term.
* **What It Lacks**: Neither path currently uses live CMEMS/GFS/HYCOM observations, so the field is a modeled prototype rather than an operational forecast or hindcast.
* **Engineering Solution**:
  * Integrate with the **Copernicus Marine Environment Monitoring Service (CMEMS)** Global Ocean Physics Analysis (0.083° grid) or **NOAA GFS / HYCOM** APIs.
  * Interpolate $(u, v)$ velocity vectors dynamically along the particle's hourly backtrack path.

### 2.2 Simplified Petroleum Weathering Models
* **Current State**: The weathering endpoint and forward forecast run simplified evaporation, emulsification, and Fay-spreading calculations. Static Bonn-matrix volume estimation is also retained at detection time.
* **What It Lacks**: Real petroleum undergoes rapid physical and chemical transformation that is not yet calibrated to the sampled oil:
  * **Evaporation**: Up to $50\%$ of light hydrocarbon fractions evaporate within the first 24 hours.
  * **Emulsification ("Chocolate Mousse")**: Water-in-oil emulsification increases slick volume by up to $300\%$ and increases viscosity.
  * **Fay's Spreading Law**: Three distinct spreading regimes (Gravity-Inertia, Gravity-Viscous, and Surface Tension-Viscous).
* **Engineering Solution**:
  * Incorporate simplified Mackay / ADIOS2 evaporation and emulsification rate equations into `backend/services/drift_engine.py`.

### 2.3 Forward Drift & Coastal Landfall ETA Scope
* **Current State**: `GET /api/forward_drift/{scenario_id}` runs a 72-hour, hourly forward simulation with dynamic modeled vectors and checks proximity against an in-code coastal-target list.
* **What It Lacks**: It does not use authoritative coastline shapefiles or live conditions, so its ETA is a prototype planning estimate rather than an operational prediction.
* **Engineering Solution**:
  * Add a Forward Lagrangian Simulation ($+24\text{h}$, $+48\text{h}$, $+72\text{h}$).
  * Compute intersection with coastline shapefiles to provide: **"Landfall Impact ETA: 14.2 hours at Alibag Beach"**.

---

## 3. Data Engineering & AIS Scale Gaps

### 3.1 In-Memory Python Engine vs. Persistent PostGIS Database
* **Current State**: Runs in-memory Python calculations and Haversine distance functions on pre-structured scenario objects.
* **What It Lacks**: Cannot query millions of historical vessel positions across entire national Exclusive Economic Zones (EEZ).
* **Engineering Solution**:
  * Stand up a **PostgreSQL 16 + PostGIS 3.4** instance.
  * Store trajectories as `GEOMETRY(LineString, 4326)` with **GIST Spatial Indexes**.
  * Use SQL spatial functions: `ST_DWithin()`, `ST_ClosestPoint()`, `ST_Intersects()`.

### 3.2 Live AIS Stream Ingestion
* **Current State**: Scenarios are loaded from static pre-formatted files.
* **What It Lacks**: No live streaming pipeline for real-time AIS telemetry.
* **Engineering Solution**:
  * Connect a background worker to **AISStream.io** (free global WebSocket feed) or ingest NMEA 0183 AIVDM/AIVDO sentences.
  * Parse message types 1, 2, 3 (Position Reports) and 5 (Static and Voyage Data).

### 3.3 Trajectory Dead-Reckoning & Spline Curve Fitting
* **Current State**: Connects AIS waypoints with straight line segments.
* **What It Lacks**: In low-coverage areas with 30–60 minute ping intervals, linear interpolation can cut across islands or miss curved vessel turns.
* **Engineering Solution**:
  * Implement **Cubic Hermite Spline** interpolation incorporating Speed Over Ground (SOG) and Course Over Ground (COG) vectors at each waypoint.

---

## 4. User Experience & Operational Tools

### 4.1 Custom Image & Data File Upload in UI
* **Current State**: The UI allows selecting between 3 pre-built scenarios.
* **What It Lacks**: A user or judge cannot upload an arbitrary SAR image file or custom AIS CSV file to run detection on a new location.
* **Engineering Solution**:
  * Add a drag-and-drop file upload modal in the web interface that submits `.tif` or `.png` crops to `POST /api/upload_and_analyze`.

### 4.2 Automated Incident Notification Webhooks
* **Current State**: Results are displayed exclusively inside the web browser.
* **What It Lacks**: No automated push alerts to field operators.
* **Engineering Solution**:
  * Add webhook integrations (Telegram Bot, Slack, or SMS/Email via Twilio/SendGrid) triggered when attribution confidence exceeds $85\%$.

---

## 5. How to Pitch These Limitations to Hackathon Judges

## Historical Validation: MV Wakashio Backtest

`scenario_wakashio_validation` is a historical backtest, not a live incident or a claim to solve an unknown attribution. It submits a simulated post-leak SAR observation to the normal scenario CFAR, dynamic-backtrack, and AIS-correlation paths. Its weather inputs are explicitly estimated, while the public facts and reference location remain separate from the system output. The dossier reports the derived-origin offset and uses the stationary grounded AIS record as a direct spatial correlation, rather than falsely applying concealment or moving-vessel heuristics.

When presenting to NTRO / SIH judges, turn these gaps into a strength by presenting a **Clear Phase 1 (Built) vs. Phase 2 (Production Roadmap)**:

```
+-----------------------------------+-----------------------------------+
|     PHASE 1: BUILT PROTOTYPE      |      PHASE 2: PRODUCTION SCALE    |
|        (What We Demo Today)       |         (Our Deployment Plan)     |
+-----------------------------------+-----------------------------------+
| • Complete End-to-End Pipeline    | • Pretrained U-Net weights on     |
| • Reverse Lagrangian Drift Engine |   100,000+ Sentinel-1 GRD scenes  |
| • Multi-Factor AIS Correlation    | • Live AISStream.io WebSockets    |
| • Look-Alike False Positive Filter| • Enterprise PostGIS Database     |
| • Interactive C2 Web Dashboard    | • Copernicus CMEMS Gridded Weather|
| • MARPOL Forensic Dossier Export  | • Dark Vessel SAR Radar Spotting  |
+-----------------------------------+-----------------------------------+
```
