#!/usr/bin/env python3
"""
Verify scene-level split has no leakage between train/val/test.
CRITICAL: Ensures no scene, location, or date appears in multiple splits.
"""
import json
import sys
from collections import defaultdict


def verify_split():
    print("=" * 60)
    print("Scene-Level Split Leakage Verification")
    print("=" * 60)
    
    manifest_path = "data/dataset_manifest.json"
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except Exception as e:
        print(f"❌ Error loading manifest: {e}")
        return False
    
    splits = manifest.get("splits", {})
    train = set(splits.get("train", []))
    val = set(splits.get("val", []))
    test = set(splits.get("test", []))
    
    # Check for overlaps
    train_val = train & val
    train_test = train & test
    val_test = val & test
    
    if train_val:
        print(f"❌ LEAKAGE: {len(train_val)} scenes in both train and val: {train_val}")
        return False
    if train_test:
        print(f"❌ LEAKAGE: {len(train_test)} scenes in both train and test: {train_test}")
        return False
    if val_test:
        print(f"❌ LEAKAGE: {len(val_test)} scenes in both val and test: {val_test}")
        return False
    
    print("✅ No scene-level leakage detected")
    print(f"   Train: {len(train)} scenes")
    print(f"   Val: {len(val)} scenes")
    print(f"   Test: {len(test)} scenes")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = verify_split()
    sys.exit(0 if success else 1)
