"""Image quality assessment."""

from __future__ import annotations

import cv2
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
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean() / 255.0)
        blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())

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
