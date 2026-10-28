# Model Validation Checklist & Report

This document addresses the critical model validation checks for the seaLens ML components.

## 1) Training Data
- **Exact datasets used**: *Not fully documented in committed code.* The U-Net architecture exists in `ml_engine/unet_model.py` but training scripts/datasets are not present in the repo.
- **Number of SAR images**: Unknown (not specified)
- **Oil-spill vs non-spill examples**: Unknown
- **Licenses**: Unknown - must be verified before public release
- **Synthetic vs real**: Many demo scenarios are synthetic/georeferenced. Real public Sentinel-1 RTC path exists. **Assumption: mixed/synthetic-heavy for demos.**

## 2) Dataset Split
- **Requirement**: Train/val/test must not overlap by scene, location, or date. Random tile splits from same image cause leakage.
- **Status**: **Not verified/committed**. Need to ensure scene-level (not tile-level) splitting.

## 3) Metrics on Held-Out Test Set
Required metrics (not committed in repo):
- **Precision, Recall, F1** (slick segmentation)
- **IoU/Dice** 
- **False Positive Rate** (critical - look-alikes)
- **Status**: **Missing** - need evaluation script + held-out test results

## 4) Baseline Comparison
- **Planned**: Compare U-Net vs thresholding/texture/CFAR approaches
- **Status**: CFAR exists separately; systematic baseline comparison not documented

## 5) Threshold Selection
- **Current**: Various thresholds used in code (look-alike filters have wind thresholds)
- **Requirement**: Select on validation set, lock before test evaluation
- **Status**: **Needs documentation**

## 6) Visual Review
Must inspect: TP, FP, missed spills, ships, coastlines, wind shadows, low-wind zones, rain cells. **Status**: Manual review needed.

## 7) Geographic Robustness
Test on region/date not in training. **Status**: Unknown - risk of poor generalization.

## 8) Calibration
Check if "90% confidence" means ~90% correct. **Status**: Not calibrated/validated. **Do not present confidence as certainty.**

## 9) CFAR Validation (Separate)
Ship/radar detection needs its own precision/recall and matching tolerance. Not validated by oil-spill U-Net metrics. **Status**: Needs separate evaluation.

## 10) Reproducibility
Need: checkpoint, training config, random seed, package versions, dataset manifest, evaluation outputs.
- **Checkpoint**: `ml_engine/checkpoints/sar_unet_oil_spill.pt` (may or may not exist)
- **Status**: **Partially missing**

## 11) Honest Model Card
**What it can detect**: Dark slick-like features in SAR under certain conditions (demo)
**What it cannot detect**: Small sheens, emulsions in high wind, many look-alikes, guarantee attribution
**Known failure cases**: Wind shadows, biogenic films, low/high wind, rain cells, ships/coastline artifacts
**Important**: Provides **investigative leads, not proof of responsibility**. All outputs are probabilistic.

## Action Items
- [ ] Create `ml_engine/training/` with training scripts and config
- [ ] Create `data/dataset_manifest.json` with sources, licenses, splits
- [ ] Create `evaluation/` with test results and metrics
- [ ] Document train/val/test split by scene
- [ ] Run baseline comparisons
- [ ] Calibrate confidence scores
- [ ] Validate CFAR separately
