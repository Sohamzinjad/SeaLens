# Real-SAR benchmark data plan

## Selected independent test benchmark

Use the **Trujillo-Acatitla et al. Sentinel-1 SAR Oil Spill Dataset, Part III**
as the first held-out evaluation set, not as training data. It contains 150 oil,
150 look-alike, and 150 no-oil test images with corresponding masks (9.9 GB).
It provides Sentinel-1 Sigma0 VV/VH dB inputs and ground truth, but masks are
not georeferenced. Cite DOI `10.5281/zenodo.13761290` and read the dataset's
licence/terms before downloading or redistributing it.

## Training and validation candidate

Parts I and II of the same Zenodo collection provide training/validation data,
but Part I alone is 40.7 GB. Do not download it automatically on a presentation
machine. Obtain it only after confirming available disk capacity, the Zenodo
terms, and that the team accepts the download.

## Recommended procedure

1. Download Part III manually from its Zenodo record and retain the citation,
   checksum, and licence text alongside the archive.
2. Extract it outside the Git repository, then create a SeaLens manifest with
   paired prediction and truth mask paths.
3. Run `python -m ml_engine.evaluate_benchmark <manifest>`.
4. Report metrics as **held-out evaluation on this specific benchmark**, not as
   global operational accuracy. Include class-wise results for oil, look-alike,
   and no-oil controls.
5. Only after baseline measurement, decide whether to fine-tune using Parts I
   and II. Keep the test set untouched.

## Secondary generalisation check

The 2025 PANGAEA Eastern Mediterranean dataset includes oil slicks and
look-alikes with Pascal VOC annotations. It is a useful region-shift check, but
its labels are object annotations rather than directly interchangeable raster
masks. Convert and validate carefully before comparing it with pixel IoU.
