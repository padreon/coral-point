"""Unit tests for src/core/multivariate.py."""

import numpy as np
import pytest
from src.core.multivariate import (
    bray_curtis_matrix,
    pcoa,
    hierarchical_clusters,
    permanova,
    simper,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def identical_matrix():
    """Two identical sites → BC distance = 0."""
    return np.array([[0.5, 0.3, 0.2], [0.5, 0.3, 0.2]], dtype=float)


@pytest.fixture
def disjoint_matrix():
    """Two completely different sites → BC distance = 1."""
    return np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=float)


@pytest.fixture
def four_site_matrix():
    """4 sites, 3 species — used for PERMANOVA."""
    return np.array([
        [0.8, 0.1, 0.1],
        [0.7, 0.2, 0.1],
        [0.1, 0.1, 0.8],
        [0.1, 0.2, 0.7],
    ], dtype=float)


# ---------------------------------------------------------------------------
# bray_curtis_matrix
# ---------------------------------------------------------------------------

class TestBrayCurtisMatrix:
    def test_identical_sites(self, identical_matrix):
        bc = bray_curtis_matrix(identical_matrix)
        assert bc.shape == (2, 2)
        assert bc[0, 1] == pytest.approx(0.0, abs=1e-10)

    def test_disjoint_sites(self, disjoint_matrix):
        bc = bray_curtis_matrix(disjoint_matrix)
        assert bc[0, 1] == pytest.approx(1.0, abs=1e-10)

    def test_symmetric(self, four_site_matrix):
        bc = bray_curtis_matrix(four_site_matrix)
        assert np.allclose(bc, bc.T)

    def test_diagonal_zero(self, four_site_matrix):
        bc = bray_curtis_matrix(four_site_matrix)
        assert np.allclose(np.diag(bc), 0.0)

    def test_range_0_to_1(self, four_site_matrix):
        bc = bray_curtis_matrix(four_site_matrix)
        assert (bc >= 0).all() and (bc <= 1 + 1e-10).all()


# ---------------------------------------------------------------------------
# pcoa
# ---------------------------------------------------------------------------

class TestPCoA:
    def test_output_keys(self, four_site_matrix):
        bc = bray_curtis_matrix(four_site_matrix)
        result = pcoa(bc)
        assert "coords" in result
        assert "eigenvalues" in result
        assert "variance_explained" in result

    def test_coords_shape(self, four_site_matrix):
        bc = bray_curtis_matrix(four_site_matrix)
        result = pcoa(bc, n_axes=2)
        assert result["coords"].shape == (4, 2)

    def test_variance_explained_sum_leq_1(self, four_site_matrix):
        bc = bray_curtis_matrix(four_site_matrix)
        result = pcoa(bc, n_axes=2)
        total = sum(result["variance_explained"])
        assert 0.0 <= total <= 1.0 + 1e-6

    def test_two_point_distance_preserved(self):
        # Two sites at BC distance d → PCoA axis 1 coordinate separation ≈ d
        mat = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=float)
        bc = bray_curtis_matrix(mat)
        d = bc[0, 1]
        result = pcoa(bc, n_axes=1)
        coords = result["coords"]
        separation = abs(float(coords[0, 0]) - float(coords[1, 0]))
        assert separation == pytest.approx(d, rel=0.01)


# ---------------------------------------------------------------------------
# hierarchical_clusters
# ---------------------------------------------------------------------------

class TestHierarchicalClusters:
    def test_returns_linkage_and_method(self, four_site_matrix):
        bc = bray_curtis_matrix(four_site_matrix)
        result = hierarchical_clusters(bc)
        assert "linkage" in result
        assert result["method"] == "average"
        # scipy linkage shape: (n-1) × 4
        assert result["linkage"].shape == (3, 4)


# ---------------------------------------------------------------------------
# permanova
# ---------------------------------------------------------------------------

class TestPermanova:
    def test_well_separated_groups_significant(self):
        # 8 sites (4 per group): groups are maximally separated.
        # With C(8,4)=70 possible splits only 2 give F >= observed → p ≈ 0.03.
        mat = np.array([
            [0.90, 0.05, 0.05],
            [0.85, 0.10, 0.05],
            [0.88, 0.07, 0.05],
            [0.87, 0.08, 0.05],
            [0.05, 0.05, 0.90],
            [0.05, 0.10, 0.85],
            [0.05, 0.07, 0.88],
            [0.05, 0.08, 0.87],
        ], dtype=float)
        bc = bray_curtis_matrix(mat)
        labels = ["A", "A", "A", "A", "B", "B", "B", "B"]
        result = permanova(bc, labels, permutations=999, seed=0)
        assert "error" not in result
        assert result["significant"] is True
        assert result["p_value"] <= 0.05

    def test_identical_groups_not_significant(self):
        # All sites identical → BC = 0 everywhere → F = 0 → all permutations
        # also give F = 0 → count_ge = permutations → p = 1.0 → not significant.
        mat = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5], [0.5, 0.5]], dtype=float)
        bc = bray_curtis_matrix(mat)
        labels = ["A", "A", "B", "B"]
        result = permanova(bc, labels, permutations=199, seed=42)
        assert "error" not in result
        assert result["significant"] is False

    def test_error_fewer_than_2_groups(self, four_site_matrix):
        bc = bray_curtis_matrix(four_site_matrix)
        result = permanova(bc, ["A", "A", "A", "A"], permutations=9)
        assert "error" in result

    def test_error_group_with_one_sample(self, four_site_matrix):
        bc = bray_curtis_matrix(four_site_matrix)
        result = permanova(bc, ["A", "A", "A", "B"], permutations=9)
        assert "error" in result

    def test_reproducible_with_seed(self, four_site_matrix):
        bc = bray_curtis_matrix(four_site_matrix)
        labels = ["A", "A", "B", "B"]
        r1 = permanova(bc, labels, permutations=99, seed=7)
        r2 = permanova(bc, labels, permutations=99, seed=7)
        assert r1["p_value"] == r2["p_value"]


# ---------------------------------------------------------------------------
# simper
# ---------------------------------------------------------------------------

class TestSIMPER:
    def test_returns_sorted_descending(self, four_site_matrix):
        codes = ["HC", "DC", "MA"]
        labels = ["A", "A", "B", "B"]
        result = simper(four_site_matrix, codes, labels, "A", "B")
        contribs = [r["avg_contribution"] for r in result]
        assert contribs == sorted(contribs, reverse=True)

    def test_cumulative_reaches_100(self, four_site_matrix):
        codes = ["HC", "DC", "MA"]
        labels = ["A", "A", "B", "B"]
        result = simper(four_site_matrix, codes, labels, "A", "B")
        assert result[-1]["cumulative_pct"] == pytest.approx(100.0, abs=0.1)

    def test_missing_group_returns_empty(self, four_site_matrix):
        codes = ["HC", "DC", "MA"]
        labels = ["A", "A", "B", "B"]
        result = simper(four_site_matrix, codes, labels, "A", "C")
        assert result == []
