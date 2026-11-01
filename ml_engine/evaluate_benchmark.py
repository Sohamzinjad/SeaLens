"""Evaluate segmentation masks from a labelled benchmark manifest.

The repository deliberately ships no claimed real-oil-spill labels.  This
utility makes metrics reproducible once an authorised benchmark is supplied.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

import cv2
import numpy as np


def binary_metrics(prediction: np.ndarray, target: np.ndarray) -> Dict[str, float]:
    pred = prediction.astype(bool)
    truth = target.astype(bool)
    tp = int(np.logical_and(pred, truth).sum())
    fp = int(np.logical_and(pred, ~truth).sum())
    fn = int(np.logical_and(~pred, truth).sum())
    tn = int(np.logical_and(~pred, ~truth).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "iou": iou,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
    }


def evaluate_manifest(path: Path, threshold: int = 127) -> Dict[str, float]:
    manifest = json.loads(path.read_text())
    samples = manifest.get("samples", [])
    if not samples:
        raise ValueError("Benchmark manifest has no labelled samples")
    totals: Dict[str, float] = {"precision": 0.0, "recall": 0.0, "iou": 0.0, "false_positive_rate": 0.0}
    for sample in samples:
        prediction = cv2.imread(str(path.parent / sample["prediction_mask"]), cv2.IMREAD_GRAYSCALE)
        target = cv2.imread(str(path.parent / sample["ground_truth_mask"]), cv2.IMREAD_GRAYSCALE)
        if prediction is None or target is None or prediction.shape != target.shape:
            raise ValueError(f"Invalid matching masks for {sample.get('id', 'unknown')}")
        metrics = binary_metrics(prediction >= threshold, target >= threshold)
        for key, value in metrics.items():
            totals[key] += value
    return {key: round(value / len(samples), 4) for key, value in totals.items()} | {"samples": len(samples)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--threshold", type=int, default=127)
    args = parser.parse_args()
    print(json.dumps(evaluate_manifest(args.manifest, args.threshold), indent=2))
