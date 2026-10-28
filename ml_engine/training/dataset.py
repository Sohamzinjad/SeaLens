"""
Scene-level SAR dataset loader.
CRITICAL: Must load by scene_id to prevent tile-level data leakage.
"""
import os
import json
from pathlib import Path


class SARSpillDataset:
    def __init__(self, images_dir, masks_dir, scene_list, transform=None):
        self.images_dir = Path(images_dir)
        self.masks_dir = Path(masks_dir)
        self.scene_list = set(scene_list)
        self.transform = transform
        self.samples = []
        self._load_samples()
    
    def _load_samples(self):
        # Load only samples from specified scenes
        manifest_path = Path("data/dataset_manifest.json")
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
        # In production, scan for paired images/masks and filter by scene_id
        print(f"Loading samples for {len(self.scene_list)} scenes (scene-level split)")
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        raise NotImplementedError("Implement with rasterio/tifffile")
