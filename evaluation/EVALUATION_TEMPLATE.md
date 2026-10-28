# Evaluation Template

## Test Set Results (Held-Out)
| Metric | Value | Notes |
| :-- | :-- | :-- |
| Precision | TBD | |
| Recall | TBD | |
| F1-Score | TBD | |
| IoU | TBD | |
| Dice | TBD | |
| False Positive Rate | TBD | Critical for look-alikes |
| True Positives | TBD | |
| False Positives | TBD | |
| False Negatives | TBD | |

## Baseline Comparison
| Method | Precision | Recall | F1 | Notes |
| :-- | :-- | :-- | :-- | :-- |
| Thresholding | TBD | TBD | TBD | |
| Texture/CFAR-based | TBD | TBD | TBD | |
| U-Net (proposed) | TBD | TBD | TBD | |

## Visual Review
- [ ] True positives inspected
- [ ] False positives inspected (ships, wind shadows, biogenic, rain)
- [ ] Missed spills inspected
- [ ] Coastline artifacts reviewed
- [ ] Geographic generalization tested

## Calibration
- [ ] Confidence calibration curve generated
- [ ] "90% confidence" validated

## CFAR Validation (Separate)
- [ ] Ship detection precision/recall
- [ ] Matching tolerance defined
