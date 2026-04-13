"""Tests for enrichment pipeline (cost, kcal, yield) using HTML fixtures."""
from __future__ import annotations

import statistics
from pathlib import Path

import pytest

from card_engine.enrichment.cost_engine import run_cost_engine, _aggregate_range
from card_engine.enrichment.kcal_engine import run_kcal_engine
from card_engine.enrichment.yield_engine import run_yield_engine, _estimate_yield_from_ingredients
from card_engine.models import IngredientLine, Range
from card_engine.providers.base import extract_from_html

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Provider extraction tests (fixture-based, no live HTTP)
# ---------------------------------------------------------------------------

class TestSainsburysProvider:
    def test_price_extracted(self):
        html = _load_fixture("sainsburys_beef_mince.html")
        result = extract_from_html(html, "https://www.sainsburys.co.uk/gol-ui/product/beef-mince")
        assert result.provider == "sainsburys"
        assert result.price_gbp == pytest.approx(3.50, rel=0.01)

    def test_pack_size_from_jsonld(self):
        html = _load_fixture("sainsburys_beef_mince.html")
        result = extract_from_html(html, "https://www.sainsburys.co.uk/gol-ui/product/beef-mince")
        assert result.pack_size_g == pytest.approx(500.0, rel=0.01)

    def test_kcal_per_100g(self):
        html = _load_fixture("sainsburys_beef_mince.html")
        result = extract_from_html(html, "https://www.sainsburys.co.uk/gol-ui/product/beef-mince")
        assert result.kcal_per_100g == pytest.approx(209.0, rel=0.01)

    def test_cost_per_100g_derived(self):
        html = _load_fixture("sainsburys_beef_mince.html")
        result = extract_from_html(html, "https://www.sainsburys.co.uk/gol-ui/product/beef-mince")
        # £3.50 / 5 (500g / 100) = £0.70 per 100g
        assert result.cost_per_100g == pytest.approx(0.70, rel=0.01)


class TestAsdaProvider:
    def test_price_extracted(self):
        html = _load_fixture("asda_chopped_tomatoes.html")
        result = extract_from_html(html, "https://www.asda.com/product/chopped-tomatoes")
        assert result.provider == "asda"
        assert result.price_gbp == pytest.approx(0.45, rel=0.01)

    def test_kcal_from_table(self):
        html = _load_fixture("asda_chopped_tomatoes.html")
        result = extract_from_html(html, "https://www.asda.com/product/chopped-tomatoes")
        assert result.kcal_per_100g == pytest.approx(22.0, rel=0.01)


class TestTescoProvider:
    def test_price_extracted(self):
        html = _load_fixture("tesco_kidney_beans.html")
        result = extract_from_html(html, "https://www.tesco.com/groceries/kidney-beans")
        assert result.provider == "tesco"
        assert result.price_gbp == pytest.approx(0.55, rel=0.01)

    def test_pack_size_from_jsonld(self):
        html = _load_fixture("tesco_kidney_beans.html")
        result = extract_from_html(html, "https://www.tesco.com/groceries/kidney-beans")
        assert result.pack_size_g == pytest.approx(400.0, rel=0.01)


# ---------------------------------------------------------------------------
# Normalisation / aggregation tests
# ---------------------------------------------------------------------------

class TestAggregateRange:
    def test_single_value(self):
        rng = _aggregate_range([1.0])
        assert rng.low == 1.0
        assert rng.mid == 1.0
        assert rng.high == 1.0

    def test_three_values(self):
        rng = _aggregate_range([1.0, 2.0, 3.0])
        assert rng.low == 1.0
        assert rng.mid == 2.0
        assert rng.high == 3.0

    def test_empty(self):
        rng = _aggregate_range([])
        assert rng.low == 0.0
        assert rng.mid == 0.0
        assert rng.high == 0.0

    def test_median_even(self):
        rng = _aggregate_range([1.0, 2.0, 3.0, 4.0])
        assert rng.mid == statistics.median([1.0, 2.0, 3.0, 4.0])


# ---------------------------------------------------------------------------
# Cost engine tests (mocked fetch)
# ---------------------------------------------------------------------------

class TestCostEngine:
    def _make_ingredient(self, key, qty, unit):
        return IngredientLine(key=key, raw_text="", quantity=qty, unit=unit, name=key)

    def test_used_cost_computed(self):
        html = _load_fixture("sainsburys_beef_mince.html")

        def fake_fetch(url):
            return html

        ing = self._make_ingredient("beef_mince", 500.0, "g")
        evidence = {"beef_mince": ["https://www.sainsburys.co.uk/gol-ui/product/beef-mince"]}
        results = run_cost_engine([ing], evidence, fetch_fn=fake_fetch)
        assert len(results) == 1
        # 500g * £0.70/100g = £3.50
        assert results[0].used_cost_mid == pytest.approx(3.50, rel=0.01)

    def test_missing_evidence_skipped(self):
        ing = self._make_ingredient("mystery_ingredient", 100.0, "g")
        results = run_cost_engine([ing], {})
        assert results == []

    def test_multiple_urls_aggregation(self):
        html1 = _load_fixture("sainsburys_beef_mince.html")
        html2 = _load_fixture("tesco_kidney_beans.html")

        def fake_fetch(url):
            if "sainsburys" in url:
                return html1
            return html2

        # Use beef_mince ingredient with two URLs
        ing = self._make_ingredient("beef_mince", 500.0, "g")
        evidence = {
            "beef_mince": [
                "https://www.sainsburys.co.uk/product/beef",
                "https://www.tesco.com/product/beef",
            ]
        }
        results = run_cost_engine([ing], evidence, fetch_fn=fake_fetch)
        assert len(results) == 1
        # Should have low, mid, high
        assert results[0].range.low <= results[0].range.mid <= results[0].range.high


# ---------------------------------------------------------------------------
# Kcal engine tests
# ---------------------------------------------------------------------------

class TestKcalEngine:
    def _make_ingredient(self, key, qty, unit):
        return IngredientLine(key=key, raw_text="", quantity=qty, unit=unit, name=key)

    def test_kcal_computed(self):
        html = _load_fixture("sainsburys_beef_mince.html")

        def fake_fetch(url):
            return html

        ing = self._make_ingredient("beef_mince", 500.0, "g")
        evidence = {"beef_mince": ["https://www.sainsburys.co.uk/product/beef"]}
        results = run_kcal_engine([ing], evidence, fetch_fn=fake_fetch)
        assert len(results) == 1
        # 500g * 209 kcal/100g = 1045 kcal
        assert results[0].total_kcal_mid == pytest.approx(1045.0, rel=0.01)


# ---------------------------------------------------------------------------
# Yield engine tests
# ---------------------------------------------------------------------------

class TestYieldEngine:
    def test_default_portions_when_no_urls(self):
        result = run_yield_engine([], [])
        assert result.portions == 10

    def test_heuristic_yield_from_ingredients(self):
        ings = [
            IngredientLine("flour", "", 500.0, "g", "flour"),
            IngredientLine("water", "", 300.0, "ml", "water"),
        ]
        total = _estimate_yield_from_ingredients(ings)
        assert total == pytest.approx(800.0, rel=0.01)

    def test_heuristic_yield_no_measurable_units(self):
        ings = [
            IngredientLine("garlic", "", 3.0, "clove", "garlic"),
        ]
        total = _estimate_yield_from_ingredients(ings)
        assert total is None

    def test_yield_from_html_fixture(self):
        """Portions detected from a page that mentions 'Serves 4'."""
        html = "<html><body>Serves 4 people</body></html>"

        def fake_fetch(url):
            return html

        result = run_yield_engine([], ["https://example.com/recipe"], fetch_fn=fake_fetch)
        assert result.portions == 4
