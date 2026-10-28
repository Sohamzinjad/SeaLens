Offline Demo Package
====================

This folder is for a self-contained offline demo that works without internet.

Add the following small files here:
- small_sar_crop.tif (small Sentinel-1 crop, ~few MB max)
- ais_subset.csv (small NOAA AIS subset, filtered for demo bbox/time)
- metocean_cache.json (minimal GFS/Copernicus style fields for demo)

The app will prefer these when offline/fallback mode is active.
