"""
Welford's algorithm for online mean and variance calculation.

This allows computing running statistics without storing all historical values.
See: https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Welford's_online_algorithm
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class WelfordState:
    """State for Welford's online algorithm."""

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def update(self, value: float) -> None:
        """Add a new value to the running statistics."""
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def variance(self) -> float:
        """Population variance."""
        if self.count < 1:
            return 0.0
        return self.m2 / self.count

    @property
    def sample_variance(self) -> float:
        """Sample variance (Bessel's correction)."""
        if self.count < 2:
            return 0.0
        return self.m2 / (self.count - 1)

    @property
    def std_dev(self) -> float:
        """Population standard deviation."""
        return math.sqrt(self.variance)

    @property
    def sample_std_dev(self) -> float:
        """Sample standard deviation."""
        return math.sqrt(self.sample_variance)

    def merge(self, other: WelfordState) -> WelfordState:
        """
        Merge two Welford states (parallel/batch updates).

        This uses Chan's parallel algorithm for combining running statistics.
        """
        if other.count == 0:
            return WelfordState(count=self.count, mean=self.mean, m2=self.m2)
        if self.count == 0:
            return WelfordState(count=other.count, mean=other.mean, m2=other.m2)

        combined_count = self.count + other.count
        delta = other.mean - self.mean
        combined_mean = self.mean + delta * other.count / combined_count
        combined_m2 = (
            self.m2
            + other.m2
            + delta * delta * self.count * other.count / combined_count
        )

        return WelfordState(
            count=combined_count,
            mean=combined_mean,
            m2=combined_m2,
        )


def get_lead_time_bucket(lead_time_hours: float) -> int:
    """
    Map a lead time (in hours) to a bucket.

    Buckets:
    - 0: 0-6 hours
    - 6: 6-12 hours
    - 12: 12-24 hours
    - 24: 24-48 hours
    - 48: 48+ hours
    """
    if lead_time_hours < 6:
        return 0
    elif lead_time_hours < 12:
        return 6
    elif lead_time_hours < 24:
        return 12
    elif lead_time_hours < 48:
        return 24
    else:
        return 48


# Z-scores for common prediction intervals
Z_SCORES = {
    50: 0.674,
    80: 1.282,
    90: 1.645,
    95: 1.960,
    99: 2.576,
}


def prediction_interval(
    mean: float, std_dev: float, confidence: int = 80
) -> tuple[float, float]:
    """
    Calculate a prediction interval.

    Args:
        mean: The adjusted forecast value
        std_dev: Standard deviation of historical errors
        confidence: Confidence level (50, 80, 90, 95, or 99)

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    z = Z_SCORES.get(confidence, 1.282)  # Default to 80%
    margin = z * std_dev
    return (mean - margin, mean + margin)
