# Model Transparency

## U-Net
- **Architecture**: SAROilSpillUNet (PyTorch) in `ml_engine/unet_model.py`
- **Training data**: Not fully specified in repo; checkpoint may be present at `ml_engine/checkpoints/sar_unet_oil_spill.pt` if available
- **Synthetic vs Real**: Many demo scenarios and synthetic GeoTIFFs are used. Real public Sentinel-1 RTC analysis path exists but performance varies.
- **Validated real-spill metrics**: **None documented/committed**. No published precision/recall/F1 on validated real spills in repo. Results are investigative leads only.
- **Usage**: Optional; pipeline degrades gracefully if weights missing.

## Other components
- **CFAR**: Classical (parameterized), no large labeled dataset metrics committed
- **Drift/Correlation**: Physics + heuristics; probabilistic
