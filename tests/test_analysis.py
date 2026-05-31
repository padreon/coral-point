"""Unit tests for src/core/analysis.py — Fase 1 ecological indices."""

import pytest
from src.core.analysis import (
    mortality_index,
    reef_health_category,
    coral_algae_ratio,
    berger_parker_dominance,
    hill_numbers,
    _codes_of_group,
)

GROUPS = [
    {"name": "Hard Coral", "codes": ["HC", "CB"]},
    {"name": "Dead Coral", "codes": ["DC", "DCA"]},
    {"name": "Algae", "codes": ["MA", "TA"]},
]


# ---------------------------------------------------------------------------
# _codes_of_group
# ---------------------------------------------------------------------------

class TestCodesOfGroup:
    def test_exact_match(self):
        assert _codes_of_group(GROUPS, "Hard Coral") == {"HC", "CB"}

    def test_case_insensitive(self):
        assert _codes_of_group(GROUPS, "hard coral") == {"HC", "CB"}

    def test_missing_group_returns_empty(self):
        assert _codes_of_group(GROUPS, "Zoanthids") == set()

    def test_empty_groups(self):
        assert _codes_of_group([], "Hard Coral") == set()


# ---------------------------------------------------------------------------
# mortality_index
# ---------------------------------------------------------------------------

class TestMortalityIndex:
    def test_basic(self):
        labels = ["HC", "HC", "DC", "DC"]  # live=2, dead=2 → MI=0.5
        assert mortality_index(labels, GROUPS) == 0.5

    def test_no_dead(self):
        labels = ["HC", "HC", "HC"]
        assert mortality_index(labels, GROUPS) == 0.0

    def test_all_dead(self):
        labels = ["DC", "DC"]
        assert mortality_index(labels, GROUPS) == 1.0

    def test_returns_none_when_no_hc_or_dc(self):
        labels = ["MA", "TA", "MA"]
        assert mortality_index(labels, GROUPS) is None

    def test_empty_labels(self):
        assert mortality_index([], GROUPS) is None

    def test_manual_value(self):
        # 1 HC + 3 DC → MI = 3/(1+3) = 0.75
        labels = ["HC", "DC", "DC", "DC"]
        assert mortality_index(labels, GROUPS) == 0.75


# ---------------------------------------------------------------------------
# reef_health_category
# ---------------------------------------------------------------------------

class TestReefHealthCategory:
    @pytest.mark.parametrize("pct,expected_cat,expected_en", [
        (0.0,   "Buruk",       "Poor"),
        (24.9,  "Buruk",       "Poor"),
        (25.0,  "Sedang",      "Fair"),
        (49.9,  "Sedang",      "Fair"),
        (50.0,  "Baik",        "Good"),
        (74.9,  "Baik",        "Good"),
        (75.0,  "Sangat Baik", "Excellent"),
        (100.0, "Sangat Baik", "Excellent"),
    ])
    def test_thresholds(self, pct, expected_cat, expected_en):
        result = reef_health_category(pct)
        assert result["category"] == expected_cat
        assert result["category_en"] == expected_en
        assert result["live_coral_pct"] == round(pct, 2)


# ---------------------------------------------------------------------------
# coral_algae_ratio
# ---------------------------------------------------------------------------

class TestCoralAlgaeRatio:
    def test_basic(self):
        # 2 HC, 2 MA → ratio = 50/50 = 1.0
        labels = ["HC", "HC", "MA", "MA"]
        assert coral_algae_ratio(labels, GROUPS) == 1.0

    def test_coral_dominated(self):
        labels = ["HC", "HC", "HC", "MA"]  # 75% / 25% = 3.0
        assert coral_algae_ratio(labels, GROUPS) == 3.0

    def test_algae_zero_returns_none(self):
        labels = ["HC", "HC", "DC"]
        assert coral_algae_ratio(labels, GROUPS) is None

    def test_empty_returns_none(self):
        assert coral_algae_ratio([], GROUPS) is None


# ---------------------------------------------------------------------------
# berger_parker_dominance
# ---------------------------------------------------------------------------

class TestBergerParker:
    def test_single_species(self):
        assert berger_parker_dominance(["HC"] * 10) == 1.0

    def test_even_two_species(self):
        assert berger_parker_dominance(["HC"] * 5 + ["DC"] * 5) == 0.5

    def test_empty(self):
        assert berger_parker_dominance([]) == 0.0

    def test_manual(self):
        # HC:3, DC:1, MA:1 → n_max=3, N=5 → 0.6
        labels = ["HC", "HC", "HC", "DC", "MA"]
        assert berger_parker_dominance(labels) == 0.6


# ---------------------------------------------------------------------------
# hill_numbers
# ---------------------------------------------------------------------------

class TestHillNumbers:
    def test_empty(self):
        h = hill_numbers([])
        assert h == {"q0": 0, "q1": 0.0, "q2": 0.0}

    def test_single_species(self):
        h = hill_numbers(["HC"] * 10)
        assert h["q0"] == 1
        assert h["q1"] == 1.0
        assert h["q2"] == 1.0

    def test_perfectly_even_two_species(self):
        # Two equally abundant species: H'=ln(2), q1=2, D=0.5 q2=2, q0=2
        labels = ["HC"] * 50 + ["DC"] * 50
        h = hill_numbers(labels)
        assert h["q0"] == 2
        assert abs(h["q1"] - 2.0) < 0.01
        assert abs(h["q2"] - 2.0) < 0.01

    def test_uniform_community_q0_eq_q1_eq_q2(self):
        # S=4 equally abundant species → q0=q1=q2=4
        labels = ["A"] * 25 + ["B"] * 25 + ["C"] * 25 + ["D"] * 25
        h = hill_numbers(labels)
        assert h["q0"] == 4
        assert abs(h["q1"] - 4.0) < 0.01
        assert abs(h["q2"] - 4.0) < 0.01

    def test_q0_is_richness(self):
        labels = ["HC", "DC", "MA", "HC", "DC"]
        h = hill_numbers(labels)
        assert h["q0"] == 3
