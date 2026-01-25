"""
Statistics utilities for forecast bias correction.

Provides both standard Welford's algorithm and exponentially weighted
variants for online mean and variance calculation.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WelfordState:
    """State for Welford's online algorithm (equal weighting)."""

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


@dataclass
class EWMAState:
    """
    Exponentially weighted moving average state.

    Uses decay factor alpha where:
    - alpha = 1.0 means only the most recent value matters
    - alpha = 0.0 means all values weighted equally (approaches Welford's)
    - alpha = 0.1 gives ~10 observation half-life

    The effective sample size is approximately 2/alpha - 1.
    """

    alpha: float = 0.1  # Decay factor (higher = faster decay of old values)
    count: int = 0
    mean: float = 0.0
    var: float = 0.0  # Exponentially weighted variance

    def update(self, value: float) -> None:
        """Add a new value with exponential weighting."""
        self.count += 1

        if self.count == 1:
            # First observation
            self.mean = value
            self.var = 0.0
        else:
            # EWMA update
            delta = value - self.mean
            self.mean = self.mean + self.alpha * delta
            # Update variance using the new mean
            self.var = (1 - self.alpha) * (self.var + self.alpha * delta * delta)

    @property
    def variance(self) -> float:
        """Exponentially weighted variance."""
        return self.var

    @property
    def std_dev(self) -> float:
        """Exponentially weighted standard deviation."""
        return math.sqrt(self.var)

    @property
    def effective_n(self) -> float:
        """Approximate effective sample size."""
        if self.alpha >= 1.0:
            return 1.0
        # This is an approximation; actual effective N depends on history
        return min(self.count, (2.0 - self.alpha) / self.alpha)


# Half-life to alpha conversion: alpha = 1 - exp(-ln(2) / half_life)
def half_life_to_alpha(half_life: float) -> float:
    """
    Convert a half-life (in number of observations) to decay factor alpha.

    After `half_life` observations, older data has half the weight.
    """
    if half_life <= 0:
        return 1.0
    return 1.0 - math.exp(-math.log(2) / half_life)


# ============================================================================
# Bucketing functions
# ============================================================================


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


class Season(enum.IntEnum):
    """Meteorological seasons for the Northern Hemisphere."""

    WINTER = 0  # Dec, Jan, Feb
    SPRING = 1  # Mar, Apr, May
    SUMMER = 2  # Jun, Jul, Aug
    FALL = 3  # Sep, Oct, Nov


def get_season(dt: datetime) -> Season:
    """Get the meteorological season for a datetime."""
    month = dt.month
    if month in (12, 1, 2):
        return Season.WINTER
    elif month in (3, 4, 5):
        return Season.SPRING
    elif month in (6, 7, 8):
        return Season.SUMMER
    else:
        return Season.FALL


class TimeOfDay(enum.IntEnum):
    """Time of day buckets."""

    NIGHT = 0  # 00:00 - 06:00
    MORNING = 1  # 06:00 - 12:00
    AFTERNOON = 2  # 12:00 - 18:00
    EVENING = 3  # 18:00 - 24:00


def get_time_of_day(dt: datetime) -> TimeOfDay:
    """Get the time of day bucket for a datetime."""
    hour = dt.hour
    if hour < 6:
        return TimeOfDay.NIGHT
    elif hour < 12:
        return TimeOfDay.MORNING
    elif hour < 18:
        return TimeOfDay.AFTERNOON
    else:
        return TimeOfDay.EVENING


@dataclass(frozen=True)
class BiasBucket:
    """
    Complete bucket specification for bias statistics.

    Groups observations by lead time, season, and time of day.
    """

    lead_time: int  # Lead time bucket (0, 6, 12, 24, 48)
    season: Season
    time_of_day: TimeOfDay

    @classmethod
    def from_timestamps(
        cls, forecast_time: datetime, target_time: datetime
    ) -> BiasBucket:
        """Create a bucket from forecast and target timestamps."""
        lead_hours = (target_time - forecast_time).total_seconds() / 3600
        return cls(
            lead_time=get_lead_time_bucket(lead_hours),
            season=get_season(target_time),
            time_of_day=get_time_of_day(target_time),
        )

    def to_db_key(self) -> int:
        """
        Encode bucket as a single integer for database storage.

        Format: LLLSSTT where:
        - LLL = lead_time (0-99)
        - SS = season (0-3)
        - TT = time_of_day (0-3)
        """
        return self.lead_time * 100 + self.season * 10 + self.time_of_day

    @classmethod
    def from_db_key(cls, key: int) -> BiasBucket:
        """Decode a database key back to a bucket."""
        time_of_day = TimeOfDay(key % 10)
        season = Season((key // 10) % 10)
        lead_time = key // 100
        return cls(lead_time=lead_time, season=season, time_of_day=time_of_day)


# ============================================================================
# Prediction intervals
# ============================================================================

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
