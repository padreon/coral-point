"""Unit tests for src/core/comparison.py."""

import pytest
from src.core.comparison import bootstrap_ci, compare_groups


# ---------------------------------------------------------------------------
# bootstrap_ci
# ---------------------------------------------------------------------------

def _shannon(labels: list[str]) -> float:
    """Simple Shannon H' for testing."""
    import math
    if not labels:
        return 0.0
    counts: dict[str, int] = {}
    for lbl in labels:
        counts[lbl] = counts.get(lbl, 0) + 1
    N = len(labels)
    return -sum((c / N) * math.log(c / N) for c in counts.values())


class TestBootstrapCI:
    def test_returns_expected_keys(self):
        labels = ["HC"] * 40 + ["DC"] * 30 + ["MA"] * 30
        result = bootstrap_ci(labels, _shannon)
        assert {"value", "ci_lower", "ci_upper"} == set(result.keys())

    def test_ci_bounds_order(self):
        labels = ["HC"] * 50 + ["DC"] * 25 + ["MA"] * 25
        result = bootstrap_ci(labels, _shannon, n_boot=500)
        assert result["ci_lower"] <= result["value"] <= result["ci_upper"]

    def test_reproducible_with_seed(self):
        labels = ["HC"] * 60 + ["DC"] * 40
        r1 = bootstrap_ci(labels, _shannon, n_boot=200, seed=99)
        r2 = bootstrap_ci(labels, _shannon, n_boot=200, seed=99)
        assert r1 == r2

    def test_different_seeds_may_differ(self):
        labels = ["HC"] * 60 + ["DC"] * 40
        r1 = bootstrap_ci(labels, _shannon, n_boot=200, seed=1)
        r2 = bootstrap_ci(labels, _shannon, n_boot=200, seed=2)
        # Very unlikely to be exactly equal with different seeds
        assert r1["ci_lower"] != r2["ci_lower"] or r1["ci_upper"] != r2["ci_upper"]

    def test_empty_labels(self):
        result = bootstrap_ci([], _shannon)
        assert result == {"value": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}

    def test_single_species_ci_collapses(self):
        labels = ["HC"] * 100
        result = bootstrap_ci(labels, _shannon, n_boot=100)
        assert result["value"] == pytest.approx(0.0, abs=1e-6)
        assert result["ci_lower"] == pytest.approx(0.0, abs=1e-6)
        assert result["ci_upper"] == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# compare_groups
# ---------------------------------------------------------------------------

class TestCompareGroups:
    def test_anova_two_different_groups(self):
        groups = {
            "A": [80.0, 82.0, 78.0, 81.0, 79.0],
            "B": [20.0, 22.0, 18.0, 21.0, 19.0],
        }
        result = compare_groups(groups, method="anova")
        assert result["method"] == "anova"
        assert result["significant"] is True
        assert result["p_value"] < 0.01

    def test_kruskal_two_different_groups(self):
        groups = {
            "A": [80.0, 82.0, 78.0],
            "B": [20.0, 22.0, 18.0],
        }
        result = compare_groups(groups, method="kruskal")
        assert result["method"] == "kruskal"
        assert result["significant"] is True

    def test_auto_selects_kruskal_for_small_n(self):
        groups = {"A": [1.0, 2.0], "B": [8.0, 9.0]}
        result = compare_groups(groups, method="auto")
        assert result["method"] == "kruskal"

    def test_auto_selects_anova_for_large_n(self):
        groups = {
            "A": list(range(10, 20)),
            "B": list(range(50, 60)),
        }
        result = compare_groups(groups, method="auto")
        assert result["method"] == "anova"

    def test_error_fewer_than_two_groups(self):
        result = compare_groups({"A": [1.0, 2.0]})
        assert "error" in result

    def test_error_group_with_one_value(self):
        result = compare_groups({"A": [1.0], "B": [2.0, 3.0]})
        assert "error" in result

    def test_similar_groups_not_significant(self):
        groups = {
            "A": [50.0, 51.0, 49.0, 50.5, 50.2],
            "B": [50.1, 50.0, 49.8, 50.3, 50.4],
        }
        result = compare_groups(groups, method="anova")
        assert result["significant"] is False
