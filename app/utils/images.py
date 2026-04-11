"""Image decoding and preprocessing helpers."""

from __future__ import annotations

import base64

import cv2
import numpy as np

from app.core.exceptions import ValidationAppError


def decode_base64_image(image_base64: str) -> np.ndarray:
    """Decode a base64 image payload into a BGR numpy array."""

    payload = image_base64
    if image_base64.startswith("data:") and "," in image_base64:
        payload = image_base64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except ValueError as exc:
        raise ValidationAppError("Image payload is not valid base64.") from exc

    np_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise ValidationAppError("Unable to decode image payload.")
    return image


def crop_image(image: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    """Crop an image to a bounding box while staying inside bounds."""

    height, width = image.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(x1, width))
    x2 = max(0, min(x2, width))
    y1 = max(0, min(y1, height))
    y2 = max(0, min(y2, height))
    if x2 <= x1 or y2 <= y1:
        raise ValidationAppError("Face bounding box is invalid.")
    return image[y1:y2, x1:x2].copy()


def ensure_minimum_size(image: np.ndarray, *, min_width: int = 160, min_height: int = 160) -> None:
    """Validate that the provided image is large enough for recognition."""

    height, width = image.shape[:2]
    if width < min_width or height < min_height:
        raise ValidationAppError(
            f"Image resolution is too small. Minimum required size is {min_width}x{min_height}."
        )
