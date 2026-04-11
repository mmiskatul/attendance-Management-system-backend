"""Liveness detection abstraction."""

from __future__ import annotations

from typing import Protocol

import numpy as np
from pydantic import BaseModel


class LivenessAssessment(BaseModel):
    """Liveness decision result."""

    passed: bool
    score: float
    provider: str
    reason: str


class LivenessDetector(Protocol):
    """Liveness detector contract."""

    async def assess(self, image: np.ndarray) -> LivenessAssessment:
        """Assess liveness for a face image."""


class MockLivenessDetector:
    """Mock provider used until a real anti-spoofing model is introduced."""

    provider_name = "mock"

    async def assess(self, image: np.ndarray) -> LivenessAssessment:
        _ = image
        return LivenessAssessment(
            passed=True,
            score=0.99,
            provider=self.provider_name,
            reason="mock_liveness_bypass",
        )
