"""Unit tests for src/core/validation.py."""

from src.core.validation import (
    ValidationResult,
    validate_metadata_completeness,
    validate_sampling_consistency,
    can_run_multivariate,
)


# ---------------------------------------------------------------------------
# Minimal stub objects
# ---------------------------------------------------------------------------

class FakePoint:
    def __init__(self, label=None):
        self.label = label


class FakeAnnotation:
    def __init__(self, n_labeled=30, scale_factor=1.0):
        self.points = [FakePoint("HC")] * n_labeled + [FakePoint(None)] * 5
        self.scale_factor = scale_factor
        self.image_path = "img.jpg"


class FakeStation:
    def __init__(self, name, date=None, gps_lat=None, gps_lon=None,
                 depth_m=None, n_labeled=30, scale_factor=1.0):
        self.name = name
        self.date = date
        self.gps_lat = gps_lat
        self.gps_lon = gps_lon
        self.depth_m = depth_m
        self.annotations = [FakeAnnotation(n_labeled, scale_factor)]


class FakeProject:
    def __init__(self, stations, point_distribution="random"):
        self.stations = stations
        self.point_distribution = point_distribution

    @property
    def annotations(self):
        return [ann for st in self.stations for ann in st.annotations]


# ---------------------------------------------------------------------------
# validate_metadata_completeness
# ---------------------------------------------------------------------------

class TestValidateMetadataCompleteness:
    def test_all_empty_metadata_returns_false_for_all(self):
        project = FakeProject([
            FakeStation("S1"),
            FakeStation("S2"),
        ])
        result = validate_metadata_completeness(project)
        for key in ("temporal", "spatial", "area", "depth"):
            assert result[key].ok is False, f"Expected '{key}' to be False"
            assert len(result[key].reasons) > 0

    def test_temporal_ok_with_two_different_dates(self):
        project = FakeProject([
            FakeStation("S1", date="2024-01-15"),
            FakeStation("S2", date="2024-06-20"),
        ])
        result = validate_metadata_completeness(project)
        assert result["temporal"].ok is True

    def test_temporal_false_with_same_dates(self):
        project = FakeProject([
            FakeStation("S1", date="2024-01-15"),
            FakeStation("S2", date="2024-01-15"),
        ])
        result = validate_metadata_completeness(project)
        assert result["temporal"].ok is False

    def test_spatial_ok_with_three_gps(self):
        project = FakeProject([
            FakeStation("S1", gps_lat=-8.5, gps_lon=115.2),
            FakeStation("S2", gps_lat=-8.6, gps_lon=115.3),
            FakeStation("S3", gps_lat=-8.7, gps_lon=115.4),
        ])
        result = validate_metadata_completeness(project)
        assert result["spatial"].ok is True

    def test_spatial_false_with_only_two_gps(self):
        project = FakeProject([
            FakeStation("S1", gps_lat=-8.5, gps_lon=115.2),
            FakeStation("S2", gps_lat=-8.6, gps_lon=115.3),
            FakeStation("S3"),  # no GPS
        ])
        result = validate_metadata_completeness(project)
        assert result["spatial"].ok is False

    def test_area_ok_with_calibrated_image(self):
        project = FakeProject([
            FakeStation("S1", scale_factor=50.0),
        ])
        result = validate_metadata_completeness(project)
        assert result["area"].ok is True

    def test_area_false_when_all_uncalibrated(self):
        project = FakeProject([
            FakeStation("S1", scale_factor=1.0),
        ])
        result = validate_metadata_completeness(project)
        assert result["area"].ok is False

    def test_depth_ok_with_three_stations(self):
        project = FakeProject([
            FakeStation("S1", depth_m=3.0),
            FakeStation("S2", depth_m=6.0),
            FakeStation("S3", depth_m=10.0),
        ])
        result = validate_metadata_completeness(project)
        assert result["depth"].ok is True

    def test_depth_false_with_two_stations(self):
        project = FakeProject([
            FakeStation("S1", depth_m=3.0),
            FakeStation("S2", depth_m=6.0),
        ])
        result = validate_metadata_completeness(project)
        assert result["depth"].ok is False

    def test_never_raises_with_empty_project(self):
        project = FakeProject([])
        result = validate_metadata_completeness(project)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# validate_sampling_consistency
# ---------------------------------------------------------------------------

class TestValidateSamplingConsistency:
    def test_ok_with_consistent_counts(self):
        project = FakeProject([
            FakeStation("S1", n_labeled=30),
            FakeStation("S2", n_labeled=28),
        ])
        result = validate_sampling_consistency(project)
        assert result.ok is True

    def test_fails_when_ratio_exceeds_2(self):
        stations = [
            FakeStation("S1", n_labeled=30),
            FakeStation("S2", n_labeled=5),  # ratio = 6 > 2
        ]
        project = FakeProject(stations)
        result = validate_sampling_consistency(project)
        assert result.ok is False
        assert len(result.reasons) > 0

    def test_warning_when_labeled_below_25(self):
        project = FakeProject([
            FakeStation("S1", n_labeled=20),
            FakeStation("S2", n_labeled=22),
        ])
        result = validate_sampling_consistency(project)
        assert len(result.warnings) > 0

    def test_fails_without_point_distribution(self):
        project = FakeProject(
            [FakeStation("S1", n_labeled=30)],
            point_distribution=None,
        )
        result = validate_sampling_consistency(project)
        assert result.ok is False


# ---------------------------------------------------------------------------
# can_run_multivariate
# ---------------------------------------------------------------------------

class TestCanRunMultivariate:
    def _make_four_station_project(self):
        return FakeProject([
            FakeStation("S1", n_labeled=30),
            FakeStation("S2", n_labeled=28),
            FakeStation("S3", n_labeled=32),
            FakeStation("S4", n_labeled=29),
        ])

    def test_ok_with_four_consistent_stations(self):
        project = self._make_four_station_project()
        result = can_run_multivariate(project)
        assert result.ok is True

    def test_fails_with_fewer_than_four_stations(self):
        project = FakeProject([
            FakeStation("S1", n_labeled=30),
            FakeStation("S2", n_labeled=30),
            FakeStation("S3", n_labeled=30),
        ])
        result = can_run_multivariate(project)
        assert result.ok is False
        assert any("4" in r for r in result.reasons)

    def test_fails_when_sampling_inconsistent(self):
        # 4 stations but one with vastly different count
        project = FakeProject([
            FakeStation("S1", n_labeled=30),
            FakeStation("S2", n_labeled=30),
            FakeStation("S3", n_labeled=30),
            FakeStation("S4", n_labeled=3),  # ratio = 10 > 2
        ])
        result = can_run_multivariate(project)
        assert result.ok is False

    def test_never_raises_with_empty_project(self):
        project = FakeProject([])
        result = can_run_multivariate(project)
        assert isinstance(result, ValidationResult)
        assert result.ok is False
