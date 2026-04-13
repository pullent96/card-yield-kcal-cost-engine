from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Ingredient:
    name: str
    quantity_raw: float
    unit: str  # g/ml/each/kg/l
    yield_fraction: float = 1.0
    cost_per_raw_unit: float = 0.0   # cost per raw unit (e.g. per g)
    kcal_per_edible_unit: float = 0.0  # kcal per edible unit


@dataclass
class RecipeCard:
    name: str
    servings: int
    ingredients: list[Ingredient]
    method: list[str] = field(default_factory=list)
    total_time: str = ""
    notes: str = ""


@dataclass
class RecipeParsed:
    title: str
    ingredients_raw: list[str]  # raw text lines
    method_raw: list[str]       # raw text steps
    total_time: str = ""
    notes: str = ""
    source_file: str = ""
    content_hash: str = ""  # for dedupe
