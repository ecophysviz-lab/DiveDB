"""
Test SQL-based resampling in DuckPond.get_data() with varying frequencies

Tests the new efficient SQL-based downsampling and upsampling approach.
"""

import pytest
import pandas as pd
import numpy as np
import pyarrow as pa
from datetime import datetime
import tempfile

from DiveDB.services.duck_pond import DuckPond


@pytest.fixture
def temp_warehouse():
    """Create a temporary warehouse directory for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def duck_pond_with_data(temp_warehouse):
    """Create a DuckPond instance with test data at multiple frequencies"""
    duck_pond = DuckPond(warehouse_path=temp_warehouse)
    dataset = "test_dataset"

    # Initialize dataset
    duck_pond.ensure_dataset_initialized(dataset)

    # Create test data with different frequencies
    start_time = datetime(2024, 1, 1, 10, 0, 0)

    # High frequency data: accelerometer at 100 Hz (10 seconds)
    acc_times = pd.date_range(start=start_time, periods=1000, freq="10ms")
    acc_values = np.sin(np.linspace(0, 4 * np.pi, 1000)) * 10 + 20

    acc_times_arrow = pa.array(acc_times, type=pa.timestamp("us"))

    duck_pond.write_signal_data(
        dataset=dataset,
        metadata={"animal": "test-animal", "deployment": "test-deployment"},
        times=acc_times_arrow,
        group="signals",
        class_name="accelerometer",
        label="acc_x",
        values=acc_values.tolist(),
    )

    # Low frequency data: depth at 1 Hz (10 seconds)
    depth_times = pd.date_range(start=start_time, periods=10, freq="1s")
    depth_values = [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5]

    depth_times_arrow = pa.array(depth_times, type=pa.timestamp("us"))

    duck_pond.write_signal_data(
        dataset=dataset,
        metadata={"animal": "test-animal", "deployment": "test-deployment"},
        times=depth_times_arrow,
        group="signals",
        class_name="depth_signal",
        label="depth",
        values=depth_values,
    )

    # Medium frequency data: temperature at 10 Hz (10 seconds)
    temp_times = pd.date_range(start=start_time, periods=100, freq="100ms")
    temp_values = np.linspace(15.0, 16.0, 100).tolist()

    temp_times_arrow = pa.array(temp_times, type=pa.timestamp("us"))

    duck_pond.write_signal_data(
        dataset=dataset,
        metadata={"animal": "test-animal", "deployment": "test-deployment"},
        times=temp_times_arrow,
        group="signals",
        class_name="temperature_signal",
        label="temperature",
        values=temp_values,
    )

    return duck_pond, dataset


class TestDownsampling:
    """Test SQL-based downsampling in get_data()"""

    def test_downsample_high_frequency_data(self, duck_pond_with_data):
        """Test downsampling high frequency accelerometer data (100 Hz -> 10 Hz)"""
        duck_pond, dataset = duck_pond_with_data

        # Get accelerometer data at 10 Hz (downsampled from 100 Hz)
        result = duck_pond.get_data(
            dataset=dataset,
            labels=["acc_x"],
            frequency=10,
        )

        # Should return a DataFrame
        assert isinstance(result, pd.DataFrame)

        # Should have ~100 rows (10 seconds * 10 Hz)
        assert 95 <= len(result) <= 105  # Allow some tolerance

        # Should have datetime, label, and numeric_value columns
        assert "datetime" in result.columns
        assert "label" in result.columns
        assert "numeric_value" in result.columns

        # All labels should be acc_x
        assert (result["label"] == "acc_x").all()

        # Values should be reasonable (from the sine wave we created)
        assert result["numeric_value"].min() >= 10
        assert result["numeric_value"].max() <= 30

    def test_downsample_extreme_reduction(self, duck_pond_with_data):
        """Test extreme downsampling (100 Hz -> 1 Hz)"""
        duck_pond, dataset = duck_pond_with_data

        result = duck_pond.get_data(
            dataset=dataset,
            labels=["acc_x"],
            frequency=1,
        )

        # Should have ~10 rows (10 seconds * 1 Hz)
        assert 9 <= len(result) <= 11

        # Should maintain data integrity
        assert "datetime" in result.columns
        assert result["datetime"].is_monotonic_increasing


class TestUpsampling:
    """Test SQL-based upsampling in get_data()"""

    def test_upsample_low_frequency_data(self, duck_pond_with_data):
        """Test upsampling low frequency depth data (1 Hz -> 5 Hz)"""
        duck_pond, dataset = duck_pond_with_data

        # Get depth data at 5 Hz (upsampled from 1 Hz)
        result = duck_pond.get_data(
            dataset=dataset,
            labels=["depth"],
            frequency=5,
        )

        # Should return a DataFrame
        assert isinstance(result, pd.DataFrame)

        # Should have ~50 rows (10 seconds * 5 Hz)
        assert 45 <= len(result) <= 55

        # Values should be forward-filled from original
        assert result["numeric_value"].min() >= 4.5
        assert result["numeric_value"].max() <= 10.0


class TestMultiFrequencyAlignment:
    """Test aligning multiple signals with different native frequencies to a common target"""

    def test_align_high_and_low_frequency(self, duck_pond_with_data):
        """Test aligning 100 Hz and 1 Hz data to common 5 Hz target"""
        duck_pond, dataset = duck_pond_with_data

        # Get both accelerometer (100 Hz) and depth (1 Hz) at 5 Hz
        result = duck_pond.get_data(
            dataset=dataset,
            labels=["acc_x", "depth"],
            frequency=5,
            pivoted=True,
        )

        # Should be pivoted with both columns
        assert "acc_x" in result.columns
        assert "depth" in result.columns
        assert "datetime" in result.columns

        # Should have ~50 rows (10 seconds * 5 Hz)
        assert 45 <= len(result) <= 55

        # Both signals should have data
        assert result["acc_x"].notna().sum() > 0
        assert result["depth"].notna().sum() > 0

    def test_align_three_frequencies(self, duck_pond_with_data):
        """Test aligning three different frequencies to common target"""
        duck_pond, dataset = duck_pond_with_data

        # Get acc_x (100 Hz), temperature (10 Hz), and depth (1 Hz) all at 2 Hz
        result = duck_pond.get_data(
            dataset=dataset,
            labels=["acc_x", "temperature", "depth"],
            frequency=2,
            pivoted=True,
        )

        # Should have all three columns
        assert "acc_x" in result.columns
        assert "temperature" in result.columns
        assert "depth" in result.columns

        # Should have ~20 rows (10 seconds * 2 Hz)
        assert 18 <= len(result) <= 22

        # All signals should have data
        assert result["acc_x"].notna().sum() > 0
        assert result["temperature"].notna().sum() > 0
        assert result["depth"].notna().sum() > 0


class TestResamplingFormats:
    """Test resampling with different output formats"""

    def test_long_format_with_frequency(self, duck_pond_with_data):
        """Test getting resampled data in long format (non-pivoted)"""
        duck_pond, dataset = duck_pond_with_data

        result = duck_pond.get_data(
            dataset=dataset,
            labels=["acc_x", "depth"],
            frequency=5,
            pivoted=False,
        )

        # Should be in long format
        assert "datetime" in result.columns
        assert "label" in result.columns
        assert "numeric_value" in result.columns

        # Should have both labels
        assert set(result["label"].unique()) == {"acc_x", "depth"}

        # Should have data for both
        acc_data = result[result["label"] == "acc_x"]
        depth_data = result[result["label"] == "depth"]
        assert len(acc_data) > 0
        assert len(depth_data) > 0

    def test_pivoted_format_with_frequency(self, duck_pond_with_data):
        """Test getting resampled data in pivoted format"""
        duck_pond, dataset = duck_pond_with_data

        result = duck_pond.get_data(
            dataset=dataset,
            labels=["temperature", "depth"],
            frequency=5,
            pivoted=True,
        )

        # Should be pivoted
        assert "datetime" in result.columns
        assert "temperature" in result.columns
        assert "depth" in result.columns

        # Should NOT have label column (that's long format)
        assert "label" not in result.columns

        # Datetime should be monotonic
        assert result["datetime"].is_monotonic_increasing


class TestNoResampling:
    """Test that data without frequency parameter works as before"""

    def test_get_data_without_frequency(self, duck_pond_with_data):
        """Test that omitting frequency parameter returns DiveData object"""
        duck_pond, dataset = duck_pond_with_data

        from DiveDB.services.dive_data import DiveData

        result = duck_pond.get_data(
            dataset=dataset,
            labels=["acc_x"],
        )

        # Should return DiveData object (not DataFrame) when no frequency
        assert isinstance(result, DiveData)

    def test_pivoted_without_frequency(self, duck_pond_with_data):
        """Test pivoted data without resampling"""
        duck_pond, dataset = duck_pond_with_data

        result = duck_pond.get_data(
            dataset=dataset,
            labels=["depth"],
            pivoted=True,
        )

        # Should return DataFrame when pivoted
        assert isinstance(result, pd.DataFrame)

        # Should have original frequency data (1 Hz = ~10 rows)
        assert 9 <= len(result) <= 11


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_frequency_same_as_native(self, duck_pond_with_data):
        """Test requesting same frequency as native frequency"""
        duck_pond, dataset = duck_pond_with_data

        # Request depth at its native 1 Hz
        result = duck_pond.get_data(
            dataset=dataset,
            labels=["depth"],
            frequency=1.0,
        )

        # Should return data without modification
        assert isinstance(result, pd.DataFrame)
        assert 9 <= len(result) <= 11  # Original 10 rows

    def test_very_low_target_frequency(self, duck_pond_with_data):
        """Test with very low target frequency"""
        duck_pond, dataset = duck_pond_with_data

        # Request 0.5 Hz (one sample every 2 seconds)
        result = duck_pond.get_data(
            dataset=dataset,
            labels=["acc_x"],
            frequency=0.5,
        )

        # Should have ~5 rows (10 seconds * 0.5 Hz)
        assert 4 <= len(result) <= 6

        # Should maintain data integrity
        assert "datetime" in result.columns
        assert result["datetime"].is_monotonic_increasing

    def test_limit_with_frequency(self, duck_pond_with_data):
        """Test that limit parameter works with frequency"""
        duck_pond, dataset = duck_pond_with_data

        result = duck_pond.get_data(
            dataset=dataset,
            labels=["acc_x"],
            frequency=10,
            limit=20,
        )

        # Should respect limit
        assert len(result) == 20
