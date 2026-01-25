"""
Types and models for local forecast adjustments.
"""

from datetime import datetime

from pydantic import BaseModel

from ..sensors.types import Attribute
from .stats import Z_SCORES, Season, TimeOfDay


class BiasStats(BaseModel):
    """Statistics for a single bucket."""

    bucket: int  # Encoded bucket key
    lead_time: int  # Lead time bucket (0, 6, 12, 24, 48)
    season: Season
    time_of_day: TimeOfDay
    count: int
    mean: float  # Mean bias (forecast - observed)
    var: float  # Variance
    last_updated: datetime

    @property
    def std_dev(self) -> float:
        """Standard deviation of errors."""
        if self.var < 0:
            return 0.0
        return self.var**0.5


class AdjustedForecastValue(BaseModel):
    """A single adjusted forecast value with uncertainty."""

    measured_at: datetime
    raw_value: int  # Original forecast value (100x scaled)
    adjusted_value: int  # Bias-corrected value (100x scaled)
    std_error: float  # Standard deviation of errors (100x scaled)
    lead_time_hours: float
    bucket: int  # Encoded bucket key
    sample_count: int  # Number of samples used for this bucket

    @property
    def lower_80(self) -> int:
        """Lower bound of 80% prediction interval (100x scaled)."""
        z = Z_SCORES[80]
        return round(self.adjusted_value - z * self.std_error)

    @property
    def upper_80(self) -> int:
        """Upper bound of 80% prediction interval (100x scaled)."""
        z = Z_SCORES[80]
        return round(self.adjusted_value + z * self.std_error)


class AdjustedForecast(BaseModel):
    """An adjusted forecast with all values."""

    forecast_id: int
    sensor_id: int
    location_id: int
    attribute: Attribute
    created_at: datetime  # When the forecast was retrieved from yr.no
    values: list[AdjustedForecastValue]
