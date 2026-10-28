"""
SAR-safe augmentations for oil spill segmentation.
Avoid heavy color jitter as SAR is grayscale radar imagery.
"""
import numpy as np


def horizontal_flip(image, mask):
    if np.random.rand() > 0.5:
        return np.flip(image, axis=1).copy(), np.flip(mask, axis=1).copy()
    return image, mask


def vertical_flip(image, mask):
    if np.random.rand() > 0.5:
        return np.flip(image, axis=0).copy(), np.flip(mask, axis=0).copy()
    return image, mask


def rotate_90(image, mask, k=None):
    if k is None:
        k = np.random.randint(0, 4)
    if k == 0:
        return image, mask
    return np.rot90(image, k).copy(), np.rot90(mask, k).copy()


def apply_augmentations(image, mask):
    image, mask = horizontal_flip(image, mask)
    image, mask = vertical_flip(image, mask)
    image, mask = rotate_90(image, mask)
    return image, mask
