"""
Tests for Welford's algorithm and statistics utilities.
"""

import math

from heim.local_forecast.stats import (
    WelfordState,
    get_lead_time_bucket,
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
