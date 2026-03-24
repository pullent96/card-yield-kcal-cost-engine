from __future__ import annotations

import hashlib
import logging
import os
import re
import string
from pathlib import Path

from card_engine.models import RecipeParsed

logger = logging.getLogger(__name__)

SECTION_HEADERS = {
    "BASE", "INGREDIENTS", "METHOD", "TOTAL TIME",
    "KCAL", "ALLERGENS", "APPROXIMATE COST", "FINISH", "NOTES",
}


def _is_section_header(line: str) -> bool:
    stripped = line.strip().rstrip(":").upper()
    return stripped in SECTION_HEADERS


def _compute_hash(title: str, ingredients: list[str], method: list[str]) -> str:
    trans = str.maketrans("", "", string.punctuation)
    norm_title = title.lower().translate(trans).strip()
    norm_ing = " ".join(i.lower().translate(trans).strip() for i in ingredients)
    norm_meth = " ".join(m.lower().translate(trans).strip() for m in method)
    raw = f"{norm_title}|{norm_ing}|{norm_meth}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_block(lines: list[str], source_file: str = "") -> RecipeParsed | None:
    """Parse a single recipe block (list of lines) into a RecipeParsed."""
    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return None

    title = non_empty[0].strip()
    if not title:
        return None

    ingredients: list[str] = []
    method: list[str] = []
    total_time = ""
    notes = ""

    current_section = None
    for line in lines[1:]:
        stripped = line.strip()
        upper = stripped.rstrip(":").upper()

        if upper in SECTION_HEADERS:
            current_section = upper
            continue

        if not stripped:
            continue

        # Remove bullet
        clean = stripped.lstrip("•").strip()

        if current_section in ("BASE", "INGREDIENTS"):
            if clean:
                ingredients.append(clean)
        elif current_section == "METHOD":
            if clean:
                method.append(clean)
        elif current_section == "TOTAL TIME":
            if clean:
                total_time = (total_time + " " + clean).strip()
        elif current_section == "NOTES":
            if clean:
                notes = (notes + " " + clean).strip()
        elif current_section in ("FINISH", "ALLERGENS", "APPROXIMATE COST", "KCAL"):
            # Store these in notes for now
            notes = (notes + f" [{current_section}: {clean}]").strip()

    content_hash = _compute_hash(title, ingredients, method)
    return RecipeParsed(
        title=title,
        ingredients_raw=ingredients,
        method_raw=method,
        total_time=total_time,
        notes=notes,
        source_file=source_file,
        content_hash=content_hash,
    )


def _split_into_blocks(lines: list[str]) -> list[list[str]]:
    """Split lines into recipe blocks separated by 2+ blank lines."""
    blocks: list[list[str]] = []
    current: list[str] = []
    blank_count = 0

    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count >= 2 and current:
                blocks.append(current)
                current = []
                blank_count = 0
            else:
                current.append(line)
        else:
            blank_count = 0
            current.append(line)

    if current:
        blocks.append(current)

    return [b for b in blocks if any(l.strip() for l in b)]


def parse_file(path: str) -> list[RecipeParsed]:
    """Parse a single .txt file — may contain one or many recipes."""
    p = Path(path)
    if not p.exists():
        logger.warning("File not found: %s", path)
        return []

    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Detect if this is a multi-recipe dump (2+ blank lines separator)
    blank_runs = re.findall(r"\n{3,}", text)
    if blank_runs or p.name == "raw_dump.txt":
        blocks = _split_into_blocks(lines)
    else:
        blocks = [lines]

    results = []
    for block in blocks:
        parsed = _parse_block(block, source_file=str(p))
        if parsed and parsed.title:
            results.append(parsed)

    logger.info("Parsed %d recipe(s) from %s", len(results), path)
    return results


def parse_directory(recipes_dir: str, dedupe: bool = True) -> list[RecipeParsed]:
    """Load all .txt files from recipes_dir, optionally dedupe."""
    d = Path(recipes_dir)
    if not d.exists():
        logger.warning("Directory not found: %s", recipes_dir)
        return []

    all_recipes: list[RecipeParsed] = []
    seen_hashes: set[str] = set()

    for txt_file in sorted(d.glob("*.txt")):
        for recipe in parse_file(str(txt_file)):
            if dedupe:
                if recipe.content_hash in seen_hashes:
                    logger.info("Deduplicating recipe: %s", recipe.title)
                    continue
                seen_hashes.add(recipe.content_hash)
            all_recipes.append(recipe)

    logger.info("Total recipes loaded: %d (dedupe=%s)", len(all_recipes), dedupe)
    return all_recipes
