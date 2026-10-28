# Public real-data validation path

seaLens can discover Sentinel-1 GRD scenes and subset historical NOAA AIS
without a Copernicus account or an AIS API key. It uses public archives only.

## Default reproducible case

`GET /api/real-data/default-case` returns the selected alignment case:

- **Area:** Texas Gulf Coast (`[-95.05, 28.83, -94.69, 29.81]`)
- **SAR:** Sentinel-1A IW radiometrically terrain-corrected (RTC) scene, `2020-01-10T00:26:44Z`
- **AIS:** NOAA/BOEM MarineCadastre daily archive for `2020-01-10`

This validates source, place, and time alignment. It is **not** a labelled oil-spill
case and must not be presented as proof that an observed feature is oil.

## API flow

1. `POST /api/real-data/sentinel/search` discovers available public scenes.
2. `POST /api/real-data/sentinel/crop` range-reads one permitted public
   Sentinel-1 asset and writes a small local GeoTIFF to `data_samples/real_data/`.
3. `POST /api/real-data/analyze-crop` runs the existing Lee-filter, U-Net and
   CA-CFAR path on that real crop. It returns zero detections when appropriate;
   it never substitutes synthetic shapes or ships.
4. `POST /api/real-data/noaa-ais/import` downloads and keeps only AIS broadcasts
   inside the requested bounding box and acquisition-time window. It requires `allow_large_download: true`
   because a daily nationwide NOAA archive is typically hundreds of MB.
5. `POST /api/real-data/noaa-ais/correlate` normalizes the cached subset into
   vessel tracks and runs the existing attribution engine against an
   analyst-reviewed origin coordinate. It returns candidate rankings, never a
   claim of responsibility.

The default scene crop is an analysis-ready, georeferenced RTC COG. The generic
STAC search can also discover raw GRD measurements; those are deliberately not
cropped by this endpoint because their raster TIFFs need SAFE annotation and
calibration data before geographic analysis. Quality checks and analytical
validation remain necessary before operational interpretation.

## Attribution

Show this credit wherever a derived SAR image is displayed:

> Contains modified Copernicus Sentinel data (2024).

For the vessel records, credit **NOAA/BOEM MarineCadastre AIS**. NOAA's archive
is intended for coastal and ocean planning and is sampled at one-minute intervals;
receiver coverage gaps and missing broadcasts are possible.

## Sources

- [AWS Open Data Sentinel-1 GRD archive](https://registry.opendata.aws/sentinel-1/)
- [AWS analysis-ready Sentinel-1 RTC archive](https://registry.opendata.aws/sentinel-1-rtc-indigo/)
- [Element 84 Sentinel-1 STAC](https://earth-search.aws.element84.com/v1)
- [MarineCadastre AIS access](https://marinecadastre.gov/accessais/)
- [NOAA 2024 AIS bulk index](https://noaaocm.blob.core.windows.net/ais/csv2/csv2024/index.html)
# Real wind and ocean-current grids

The API now has a met-ocean preparation path that caches only a small spatial
and time window per incident, then uses bilinear spatial interpolation and
linear time interpolation at each 15-minute reverse-drift step:

* `POST /api/real-data/metocean/prepare` fetches credential-free NOAA NOMADS
  GFS 0.25-degree `UGRD`/`VGRD` 10-m wind subsets where the requested time is
  within the operational GFS window.
* `POST /api/real-data/metocean/backtrack` uses those cached fields with the
  existing step-wise `DriftEngine.backtrack_origin` path. Its response states
  whether wind/current data came from a provider grid or the offline fallback.
* Copernicus Marine `uo`/`vo` surface currents are fetched through the official
  Toolbox only when its local credentials have been configured. The API never
  accepts, stores, or exposes a password.

To enable currents on the Mac that runs seaLens, create a free Copernicus
Marine account, then set these values only in that Mac's terminal environment
before starting the server:

```bash
export COPERNICUSMARINE_SERVICE_USERNAME='your-account-email'
export COPERNICUSMARINE_SERVICE_PASSWORD='your-password-or-token'
```

If a historical backtest is requested, GFS is intentionally not substituted
with present-day wind: GFS is an operational forecast, not a historical
archive. Configure a Copernicus historical/reanalysis dataset through
`SEALENS_CMEMS_DATASET_ID` for a historical incident. Until both field sources
cover a step, seaLens keeps the existing modelled grid as a visibly-labelled
offline fallback. Cached grids are stored locally under
`data_samples/metocean_cache/` and are ignored by Git.
