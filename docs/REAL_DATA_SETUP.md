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
