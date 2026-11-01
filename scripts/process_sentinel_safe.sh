#!/usr/bin/env bash
# Produce a georeferenced VV Sigma0 GeoTIFF from a Sentinel-1 GRD SAFE product.
# Usage: scripts/process_sentinel_safe.sh /path/to/product.SAFE output.tif
set -euo pipefail

snap_gpt="${SEALENS_SNAP_GPT:-/Applications/esa-snap/bin/gpt}"
source_product="${1:?Provide a Sentinel-1 GRD .SAFE directory or .zip product}"
output_tif="${2:?Provide an output .tif path}"

if [[ ! -x "$snap_gpt" ]]; then
  echo "SNAP GPT was not found at $snap_gpt. Set SEALENS_SNAP_GPT to SNAP's gpt executable." >&2
  exit 1
fi
if [[ ! -e "$source_product" ]]; then
  echo "Source SAFE product does not exist: $source_product" >&2
  exit 1
fi

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/sealens-snap.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT
mkdir -p "$(dirname "$output_tif")"

"$snap_gpt" Apply-Orbit-File -Ssource="$source_product" -t "$work_dir/orbit.dim"
"$snap_gpt" ThermalNoiseRemoval -Ssource="$work_dir/orbit.dim" -t "$work_dir/noise.dim"
"$snap_gpt" Calibration -Ssource="$work_dir/noise.dim" -PoutputSigmaBand=true -t "$work_dir/sigma0.dim"
"$snap_gpt" Speckle-Filter -Ssource="$work_dir/sigma0.dim" -Pfilter="Lee" -t "$work_dir/speckle.dim"
"$snap_gpt" Terrain-Correction -Ssource="$work_dir/speckle.dim" -PsourceBands="Sigma0_VV" \
  -PmapProjection="EPSG:4326" -PpixelSpacingInMeter=10 -t "$output_tif" -f GeoTIFF

echo "Created $output_tif"
echo "Run SeaLens real-crop analysis only after visually checking the exported raster and recording its source product, processing time, and SNAP version."
