#!/bin/bash
echo "Packaging offline demo bundle..."
mkdir -p dist
zip -r dist/seaLens_offline_demo_$(date +%Y%m%d).zip \
  data_samples/real_data/offline_demo/ \
  data_samples/sample_sar_scene.tif \
  backend/scenarios_data.py \
  DEMO_FLOW.md \
  README.md \
  2>&1 | tail -5
echo "Done. Check dist/"
