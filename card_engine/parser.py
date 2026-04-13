"""Parse raw recipe text into a structured ParsedRecipe."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from card_engine.models import IngredientLine, ParsedRecipe

# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

UNIT_ALIASES: dict[str, str] = {
    "g": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "ml": "ml", "millilitre": "ml", "milliliter": "ml",
    "millilitres": "ml", "milliliters": "ml",
    "l": "l", "litre": "l", "liter": "l", "litres": "l", "liters": "l",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "cup": "cup", "cups": "cup",
    "pinch": "pinch", "bunch": "bunch", "handful": "handful",
    "tin": "tin", "tins": "tin",
    "clove": "clove", "cloves": "clove",
    "head": "head", "heads": "head",
    "can": "can", "cans": "can",
}

_UNIT_PAT = "(" + "|".join(sorted(UNIT_ALIASES.keys(), key=len, reverse=True)) + ")"
_INGREDIENT_RE = re.compile(
    r"^(?P<qty>[0-9]+(?:[./][0-9]+)?)\s*"
    r"(?P<unit>" + _UNIT_PAT + r")?\s*"
    r"(?P<name>.+)$",
    re.IGNORECASE,
)


def _slugify(text: str) -> str:
    """Convert text to a URL/key-safe slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text


def _ingredient_key(name: str) -> str:
    """Derive an underscore slug from an ingredient name."""
    slug = _slugify(name)
    return slug.replace("-", "_")


def _parse_quantity(raw: str) -> Optional[float]:
    """Parse '500', '1/2', '1.5' etc."""
    raw = raw.strip()
    if not raw:
        return None
    if "/" in raw:
        parts = raw.split("/")
        try:
            return float(parts[0]) / float(parts[1])
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_ingredient_line(line: str) -> IngredientLine:
    """Parse a single ingredient line into an IngredientLine."""
    line = line.strip()
    # Strip numbered markers: "1. " or "1) "
    line = re.sub(r"^\d+[.)]\s+", "", line)
    # Strip bullet markers: "- " or "* " or "• "
    line = re.sub(r"^[-*\u2022]\s+", "", line)
    m = _INGREDIENT_RE.match(line)
    if m:
        qty_str = m.group("qty")
        unit_str = (m.group("unit") or "").lower().strip()
        name_str = m.group("name").strip()
        unit_norm = UNIT_ALIASES.get(unit_str) if unit_str else None
        return IngredientLine(
            key=_ingredient_key(name_str),
            raw_text=line,
            quantity=_parse_quantity(qty_str),
            unit=unit_norm,
            name=name_str,
        )
    # Fallback: entire line is the name
    return IngredientLine(
        key=_ingredient_key(line),
        raw_text=line,
        quantity=None,
        unit=None,
        name=line,
    )


# ---------------------------------------------------------------------------
# Section detection
# ---------------------------------------------------------------------------

_TITLE_RE = re.compile(r"^TITLE\s*[:=]\s*(.+)$", re.IGNORECASE)
_BASE_RE = re.compile(r"^(BASE|INGREDIENTS?)\s*[:=]?\s*$", re.IGNORECASE)
_METHOD_RE = re.compile(r"^(METHOD|STEPS?|INSTRUCTIONS?)\s*[:=]?\s*$", re.IGNORECASE)
_NOTES_RE = re.compile(r"^(NOTES?|TIPS?)\s*[:=]?\s*$", re.IGNORECASE)


def parse_recipe_text(text: str) -> ParsedRecipe:
    """Parse raw recipe text into a :class:`ParsedRecipe`."""
    lines = [ln.rstrip() for ln in text.splitlines()]

    title = ""
    ingredients: list[IngredientLine] = []
    method: list[str] = []
    notes: list[str] = []

    section = "preamble"  # preamble | base | method | notes

    for line in lines:
        if not line.strip():
            continue

        m_title = _TITLE_RE.match(line.strip())
        if m_title:
            title = m_title.group(1).strip()
            section = "preamble"
            continue

        if _BASE_RE.match(line.strip()):
            section = "base"
            continue
        if _METHOD_RE.match(line.strip()):
            section = "method"
            continue
        if _NOTES_RE.match(line.strip()):
            section = "notes"
            continue

        # Implicit title: first non-blank line in preamble (no TITLE: prefix)
        if section == "preamble" and not title:
            title = line.strip()
            continue

        if section == "base":
            ingredients.append(_parse_ingredient_line(line))
        elif section == "method":
            step = re.sub(r"^[\d]+[.)]\s*", "", line.strip())
            if step:
                method.append(step)
        elif section == "notes":
            note = re.sub(r"^[-*]\s*", "", line.strip())
            if note:
                notes.append(note)

    slug = _slugify(title) if title else "recipe"
    return ParsedRecipe(
        title=title or "Untitled",
        slug=slug,
        ingredients=ingredients,
        method=method,
        notes=notes,
    )
