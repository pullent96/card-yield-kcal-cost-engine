"""Data models for the recipe card engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Parsed recipe
# ---------------------------------------------------------------------------

@dataclass
class IngredientLine:
    """A single ingredient as parsed from the BASE section."""
    key: str                     # normalised slug, e.g. "beef_mince"
    raw_text: str                # original line, e.g. "500g beef mince"
    quantity: Optional[float]    # numeric quantity, e.g. 500.0
    unit: Optional[str]          # "g", "ml", "tsp", "tbsp", "kg", "l", …
    name: str                    # human name, e.g. "beef mince"


@dataclass
class ParsedRecipe:
    """Structured recipe parsed from raw text."""
    title: str
    slug: str                        # URL-safe identifier, e.g. "chilli-con-carne"
    ingredients: list[IngredientLine] = field(default_factory=list)
    method: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Enrichment result types
# ---------------------------------------------------------------------------

@dataclass
class Range:
    low: float
    mid: float
    high: float


@dataclass
class CostResult:
    ingredient_key: str
    used_cost_mid: float
    range: Range
    source_urls: list[str] = field(default_factory=list)


@dataclass
class KcalResult:
    ingredient_key: str
    total_kcal_mid: float
    range: Range
    source_urls: list[str] = field(default_factory=list)


@dataclass
class YieldResult:
    portions: int
    total_yield_g: Optional[float]   # grams or ml; None if unknown
    source_urls: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Final recipe card
# ---------------------------------------------------------------------------

@dataclass
class RecipeCard:
    title: str
    slug: str
    portions: int
    total_yield_g: Optional[float]

    cost_low: float
    cost_mid: float
    cost_high: float
    cost_per_portion_mid: float

    kcal_low: float
    kcal_mid: float
    kcal_high: float
    kcal_per_portion_mid: float

    ingredients: list[IngredientLine]
    method: list[str]
    notes: list[str]

    cost_breakdown: list[CostResult] = field(default_factory=list)
    kcal_breakdown: list[KcalResult] = field(default_factory=list)
