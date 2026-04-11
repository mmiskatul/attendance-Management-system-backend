"""Image quality assessment."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field


class QualityAssessment(BaseModel):
    """Quality evaluation for a face image."""

    score: float
    is_acceptable: bool
    reasons: list[str] = Field(default_factory=list)
    brightness: float
    blur_variance: float


class ImageQualityService:
    """Compute image quality signals used in enrollment and recognition."""

    def assess(self, image: np.ndarray, *, min_score: float) -> QualityAssessment:
        gray = self._to_grayscale(image)
        brightness = float(gray.mean() / 255.0)
        blur_variance = float(self._laplacian_variance(gray))

        reasons: list[str] = []
        blur_score = min(blur_variance / 250.0, 1.0)
        brightness_score = max(0.0, 1.0 - abs(brightness - 0.55) / 0.55)

        if brightness < 0.20:
            reasons.append("image_too_dark")
        if brightness > 0.90:
            reasons.append("image_too_bright")
        if blur_variance < 50.0:
            reasons.append("image_too_blurry")

        score = round((0.55 * brightness_score) + (0.45 * blur_score), 4)
        return QualityAssessment(
            score=score,
            is_acceptable=score >= min_score and not reasons,
            reasons=reasons,
            brightness=round(brightness, 4),
            blur_variance=round(blur_variance, 4),
        )

    @staticmethod
    def _to_grayscale(image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            return image.astype(np.float32)
        blue = image[:, :, 0].astype(np.float32)
        green = image[:, :, 1].astype(np.float32)
        red = image[:, :, 2].astype(np.float32)
        return 0.114 * blue + 0.587 * green + 0.299 * red

    @staticmethod
    def _laplacian_variance(gray: np.ndarray) -> float:
        padded = np.pad(gray, 1, mode="edge")
        center = padded[1:-1, 1:-1]
        up = padded[:-2, 1:-1]
        down = padded[2:, 1:-1]
        left = padded[1:-1, :-2]
        right = padded[1:-1, 2:]
        laplacian = (4.0 * center) - up - down - left - right
        return float(laplacian.var())
