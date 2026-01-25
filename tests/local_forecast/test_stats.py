"""
Tests for statistics utilities.
"""

import math
from datetime import datetime

from heim.local_forecast.stats import (
    BiasBucket,
    EWMAState,
    Season,
    TimeOfDay,
    WelfordState,
    get_lead_time_bucket,
    get_season,
    get_time_of_day,
    half_life_to_alpha,
    prediction_interval,
)


class TestWelfordState:
    def test_empty_state(self) -> None:
        state = WelfordState()
        assert state.count == 0
        assert state.mean == 0.0
        assert state.variance == 0.0
        assert state.std_dev == 0.0

    def test_single_value(self) -> None:
        state = WelfordState()
        state.update(10.0)
        assert state.count == 1
        assert state.mean == 10.0
        assert state.variance == 0.0

    def test_two_values(self) -> None:
        state = WelfordState()
        state.update(10.0)
        state.update(20.0)
        assert state.count == 2
        assert state.mean == 15.0
        # Variance of [10, 20] = ((10-15)^2 + (20-15)^2) / 2 = 25
        assert state.variance == 25.0
        assert state.std_dev == 5.0

    def test_multiple_values(self) -> None:
        """Test with a known dataset."""
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        state = WelfordState()
        for v in values:
            state.update(v)

        assert state.count == 8
        assert state.mean == 5.0
        # Population variance = 4.0
        assert math.isclose(state.variance, 4.0)
        assert math.isclose(state.std_dev, 2.0)
        # Sample variance = 4.571...
        assert math.isclose(state.sample_variance, 32 / 7)

    def test_merge_empty_states(self) -> None:
        state1 = WelfordState()
        state2 = WelfordState()
        merged = state1.merge(state2)
        assert merged.count == 0
        assert merged.mean == 0.0

    def test_merge_with_empty(self) -> None:
        state1 = WelfordState()
        state1.update(10.0)
        state2 = WelfordState()

        merged = state1.merge(state2)
        assert merged.count == 1
        assert merged.mean == 10.0

        merged = state2.merge(state1)
        assert merged.count == 1
        assert merged.mean == 10.0

    def test_merge_two_states(self) -> None:
        """Test that merging produces the same result as sequential updates."""
        # Create two states with different data
        state1 = WelfordState()
        for v in [2.0, 4.0, 4.0, 4.0]:
            state1.update(v)

        state2 = WelfordState()
        for v in [5.0, 5.0, 7.0, 9.0]:
            state2.update(v)

        # Merge them
        merged = state1.merge(state2)

        # Create a sequential state with all values
        sequential = WelfordState()
        for v in [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]:
            sequential.update(v)

        assert merged.count == sequential.count
        assert math.isclose(merged.mean, sequential.mean)
        assert math.isclose(merged.m2, sequential.m2, rel_tol=1e-9)


class TestEWMAState:
    def test_empty_state(self) -> None:
        state = EWMAState(alpha=0.1)
        assert state.count == 0
        assert state.mean == 0.0
        assert state.variance == 0.0
        assert state.std_dev == 0.0

    def test_single_value(self) -> None:
        state = EWMAState(alpha=0.1)
        state.update(10.0)
        assert state.count == 1
        assert state.mean == 10.0
        assert state.variance == 0.0

    def test_two_values(self) -> None:
        state = EWMAState(alpha=0.5)  # High alpha for clear effect
        state.update(10.0)
        state.update(20.0)
        assert state.count == 2
        # With alpha=0.5: new_mean = 10 + 0.5 * (20 - 10) = 15
        assert state.mean == 15.0

    def test_decay_effect(self) -> None:
        """Test that older values have less weight."""
        # With high alpha, recent values dominate
        state_high = EWMAState(alpha=0.9)
        for v in [0.0, 0.0, 0.0, 100.0]:
            state_high.update(v)

        # With low alpha, older values have more weight
        state_low = EWMAState(alpha=0.1)
        for v in [0.0, 0.0, 0.0, 100.0]:
            state_low.update(v)

        # High alpha should be closer to 100 (recent value)
        assert state_high.mean > state_low.mean

    def test_effective_n(self) -> None:
        state = EWMAState(alpha=0.1)
        for i in range(100):
            state.update(float(i))

        # Effective N should be around 2/alpha - 1 = 19
        assert 15 < state.effective_n < 25


class TestHalfLifeToAlpha:
    def test_half_life_10(self) -> None:
        alpha = half_life_to_alpha(10)
        # After 10 observations, weight should be ~0.5
        # alpha ≈ 0.067
        assert 0.05 < alpha < 0.08

    def test_half_life_1(self) -> None:
        alpha = half_life_to_alpha(1)
        # Very fast decay
        assert alpha > 0.5

    def test_half_life_zero(self) -> None:
        alpha = half_life_to_alpha(0)
        assert alpha == 1.0


class TestLeadTimeBucket:
    def test_bucket_0_to_6(self) -> None:
        assert get_lead_time_bucket(0) == 0
        assert get_lead_time_bucket(3) == 0
        assert get_lead_time_bucket(5.9) == 0

    def test_bucket_6_to_12(self) -> None:
        assert get_lead_time_bucket(6) == 6
        assert get_lead_time_bucket(9) == 6
        assert get_lead_time_bucket(11.9) == 6

    def test_bucket_12_to_24(self) -> None:
        assert get_lead_time_bucket(12) == 12
        assert get_lead_time_bucket(18) == 12
        assert get_lead_time_bucket(23.9) == 12

    def test_bucket_24_to_48(self) -> None:
        assert get_lead_time_bucket(24) == 24
        assert get_lead_time_bucket(36) == 24
        assert get_lead_time_bucket(47.9) == 24

    def test_bucket_48_plus(self) -> None:
        assert get_lead_time_bucket(48) == 48
        assert get_lead_time_bucket(72) == 48
        assert get_lead_time_bucket(168) == 48  # 1 week


class TestSeason:
    def test_winter(self) -> None:
        assert get_season(datetime(2024, 12, 15)) == Season.WINTER
        assert get_season(datetime(2024, 1, 15)) == Season.WINTER
        assert get_season(datetime(2024, 2, 15)) == Season.WINTER

    def test_spring(self) -> None:
        assert get_season(datetime(2024, 3, 15)) == Season.SPRING
        assert get_season(datetime(2024, 4, 15)) == Season.SPRING
        assert get_season(datetime(2024, 5, 15)) == Season.SPRING

    def test_summer(self) -> None:
        assert get_season(datetime(2024, 6, 15)) == Season.SUMMER
        assert get_season(datetime(2024, 7, 15)) == Season.SUMMER
        assert get_season(datetime(2024, 8, 15)) == Season.SUMMER

    def test_fall(self) -> None:
        assert get_season(datetime(2024, 9, 15)) == Season.FALL
        assert get_season(datetime(2024, 10, 15)) == Season.FALL
        assert get_season(datetime(2024, 11, 15)) == Season.FALL


class TestTimeOfDay:
    def test_night(self) -> None:
        assert get_time_of_day(datetime(2024, 1, 1, 0, 0)) == TimeOfDay.NIGHT
        assert get_time_of_day(datetime(2024, 1, 1, 3, 0)) == TimeOfDay.NIGHT
        assert get_time_of_day(datetime(2024, 1, 1, 5, 59)) == TimeOfDay.NIGHT

    def test_morning(self) -> None:
        assert get_time_of_day(datetime(2024, 1, 1, 6, 0)) == TimeOfDay.MORNING
        assert get_time_of_day(datetime(2024, 1, 1, 9, 0)) == TimeOfDay.MORNING
        assert get_time_of_day(datetime(2024, 1, 1, 11, 59)) == TimeOfDay.MORNING

    def test_afternoon(self) -> None:
        assert get_time_of_day(datetime(2024, 1, 1, 12, 0)) == TimeOfDay.AFTERNOON
        assert get_time_of_day(datetime(2024, 1, 1, 15, 0)) == TimeOfDay.AFTERNOON
        assert get_time_of_day(datetime(2024, 1, 1, 17, 59)) == TimeOfDay.AFTERNOON

    def test_evening(self) -> None:
        assert get_time_of_day(datetime(2024, 1, 1, 18, 0)) == TimeOfDay.EVENING
        assert get_time_of_day(datetime(2024, 1, 1, 21, 0)) == TimeOfDay.EVENING
        assert get_time_of_day(datetime(2024, 1, 1, 23, 59)) == TimeOfDay.EVENING


class TestBiasBucket:
    def test_from_timestamps(self) -> None:
        forecast_time = datetime(2024, 7, 15, 10, 0)  # Summer morning
        target_time = datetime(2024, 7, 15, 14, 0)  # Summer afternoon, 4h lead

        bucket = BiasBucket.from_timestamps(forecast_time, target_time)

        assert bucket.lead_time == 0  # 0-6h bucket
        assert bucket.season == Season.SUMMER
        assert bucket.time_of_day == TimeOfDay.AFTERNOON

    def test_db_key_roundtrip(self) -> None:
        original = BiasBucket(
            lead_time=12,
            season=Season.WINTER,
            time_of_day=TimeOfDay.EVENING,
        )

        key = original.to_db_key()
        restored = BiasBucket.from_db_key(key)

        assert restored.lead_time == original.lead_time
        assert restored.season == original.season
        assert restored.time_of_day == original.time_of_day

    def test_all_bucket_combinations(self) -> None:
        """Test that all bucket combinations have unique keys."""
        keys = set()
        for lead_time in [0, 6, 12, 24, 48]:
            for season in Season:
                for time_of_day in TimeOfDay:
                    bucket = BiasBucket(
                        lead_time=lead_time,
                        season=season,
                        time_of_day=time_of_day,
                    )
                    key = bucket.to_db_key()
                    assert key not in keys, f"Duplicate key: {key}"
                    keys.add(key)

        # 5 lead times * 4 seasons * 4 times of day = 80 unique buckets
        assert len(keys) == 80


class TestFallbackLookup:
    """Tests for the fallback bucket lookup logic."""

    def test_exact_match_returned(self) -> None:
        """When exact bucket has enough data, use it."""
        from heim.local_forecast.queries import lookup_with_fallback

        bucket = BiasBucket(
            lead_time=0, season=Season.WINTER, time_of_day=TimeOfDay.MORNING
        )
        stats = {
            bucket.to_db_key(): EWMAState(alpha=0.05, count=10, mean=50.0, var=100.0),
        }

        result = lookup_with_fallback(bucket, stats, min_count=5)
        assert result.count == 10
        assert result.mean == 50.0

    def test_fallback_to_same_season(self) -> None:
        """When exact bucket is sparse, fall back to same season different time."""
        from heim.local_forecast.queries import lookup_with_fallback

        bucket = BiasBucket(
            lead_time=0, season=Season.WINTER, time_of_day=TimeOfDay.MORNING
        )
        # Exact bucket has too few samples
        exact_key = bucket.to_db_key()
        # But winter evening has enough
        fallback = BiasBucket(
            lead_time=0, season=Season.WINTER, time_of_day=TimeOfDay.EVENING
        )
        fallback_key = fallback.to_db_key()

        stats = {
            exact_key: EWMAState(alpha=0.05, count=2, mean=30.0, var=50.0),  # Too few
            fallback_key: EWMAState(
                alpha=0.05, count=10, mean=50.0, var=100.0
            ),  # Enough
        }

        result = lookup_with_fallback(bucket, stats, min_count=5)
        assert result.count == 10
        assert result.mean == 50.0

    def test_fallback_to_different_season(self) -> None:
        """When no bucket in same season has enough, try different season."""
        from heim.local_forecast.queries import lookup_with_fallback

        bucket = BiasBucket(
            lead_time=0, season=Season.WINTER, time_of_day=TimeOfDay.MORNING
        )
        # Summer morning has enough data
        fallback = BiasBucket(
            lead_time=0, season=Season.SUMMER, time_of_day=TimeOfDay.MORNING
        )
        fallback_key = fallback.to_db_key()

        stats = {
            fallback_key: EWMAState(alpha=0.05, count=10, mean=25.0, var=80.0),
        }

        result = lookup_with_fallback(bucket, stats, min_count=5)
        assert result.count == 10
        assert result.mean == 25.0

    def test_aggregate_lead_time_when_all_sparse(self) -> None:
        """When all buckets are sparse, aggregate by lead time."""
        from heim.local_forecast.queries import lookup_with_fallback

        bucket = BiasBucket(
            lead_time=0, season=Season.WINTER, time_of_day=TimeOfDay.MORNING
        )

        # Multiple sparse buckets for same lead time
        stats = {
            BiasBucket(
                lead_time=0, season=Season.WINTER, time_of_day=TimeOfDay.MORNING
            ).to_db_key(): EWMAState(alpha=0.05, count=2, mean=40.0, var=100.0),
            BiasBucket(
                lead_time=0, season=Season.SUMMER, time_of_day=TimeOfDay.EVENING
            ).to_db_key(): EWMAState(alpha=0.05, count=3, mean=60.0, var=200.0),
        }

        result = lookup_with_fallback(bucket, stats, min_count=5)
        # Should aggregate: (2*40 + 3*60) / 5 = 52
        assert result.count == 5
        assert result.mean == 52.0

    def test_no_data_returns_prior(self) -> None:
        """When no data exists, return uninformative prior."""
        from heim.local_forecast.queries import (
            DEFAULT_PRIOR_VARIANCE,
            lookup_with_fallback,
        )

        bucket = BiasBucket(
            lead_time=0, season=Season.WINTER, time_of_day=TimeOfDay.MORNING
        )
        stats: dict[int, EWMAState] = {}

        result = lookup_with_fallback(bucket, stats, min_count=5)
        assert result.count == 0
        assert result.mean == 0.0  # No bias correction
        assert result.var == DEFAULT_PRIOR_VARIANCE  # High uncertainty


class TestPredictionInterval:
    def test_80_percent_interval(self) -> None:
        lower, upper = prediction_interval(100.0, 10.0, 80)
        # z = 1.282 for 80%
        assert math.isclose(lower, 100.0 - 12.82)
        assert math.isclose(upper, 100.0 + 12.82)

    def test_95_percent_interval(self) -> None:
        lower, upper = prediction_interval(100.0, 10.0, 95)
        # z = 1.96 for 95%
        assert math.isclose(lower, 100.0 - 19.6)
        assert math.isclose(upper, 100.0 + 19.6)

    def test_zero_std_dev(self) -> None:
        lower, upper = prediction_interval(100.0, 0.0, 80)
        assert lower == 100.0
        assert upper == 100.0
