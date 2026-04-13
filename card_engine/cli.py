"""CLI entrypoint for the recipe card engine.

Usage::

    recipe-engine parse <input.txt> --out <dir>
    recipe-engine run   <input.txt> --evidence <dir> --out <dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from card_engine.enrichment import run_cost_engine, run_kcal_engine, run_yield_engine
from card_engine.exporter import export_docx
from card_engine.parser import parse_recipe_text
from card_engine.renderer import recipe_card_to_dict, render_recipe_card


# ---------------------------------------------------------------------------
# Evidence loaders
# ---------------------------------------------------------------------------

def _load_evidence(evidence_dir: Path, slug: str, kind: str) -> dict | list:
    """Load an evidence JSON file, returning {} or [] on missing."""
    path = evidence_dir / kind / f"{slug}.json"
    if not path.exists():
        return {} if kind in ("cost", "kcal") else []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Subcommand: parse
# ---------------------------------------------------------------------------

def cmd_parse(args: argparse.Namespace) -> None:
    text = Path(args.input).read_text(encoding="utf-8")
    recipe = parse_recipe_text(text)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"{recipe.slug}.parsed.json"
    data = {
        "title": recipe.title,
        "slug": recipe.slug,
        "ingredients": [
            {
                "key": i.key,
                "name": i.name,
                "raw_text": i.raw_text,
                "quantity": i.quantity,
                "unit": i.unit,
            }
            for i in recipe.ingredients
        ],
        "method": recipe.method,
        "notes": recipe.notes,
    }
    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Parsed recipe written to {out_file}")


# ---------------------------------------------------------------------------
# Subcommand: run
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    text = Path(args.input).read_text(encoding="utf-8")
    recipe = parse_recipe_text(text)

    evidence_dir = Path(args.evidence)
    cost_ev: dict = _load_evidence(evidence_dir, recipe.slug, "cost")  # type: ignore[assignment]
    kcal_ev: dict = _load_evidence(evidence_dir, recipe.slug, "kcal")  # type: ignore[assignment]
    yield_ev: list = _load_evidence(evidence_dir, recipe.slug, "yield")  # type: ignore[assignment]

    cost_results = run_cost_engine(recipe.ingredients, cost_ev)
    kcal_results = run_kcal_engine(recipe.ingredients, kcal_ev)
    yield_result = run_yield_engine(recipe.ingredients, yield_ev)

    card = render_recipe_card(recipe, cost_results, kcal_results, yield_result)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON recipe card
    json_path = out_dir / f"{recipe.slug}.recipe-card.json"
    json_path.write_text(
        json.dumps(recipe_card_to_dict(card), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Recipe card JSON written to {json_path}")

    # Write docx (one per recipe)
    docx_path = export_docx(card, out_dir)
    print(f"Recipe card DOCX written to {docx_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="recipe-engine",
        description="Recipe card yield/kcal/cost engine",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # parse sub-command
    p_parse = sub.add_parser("parse", help="Parse raw recipe text to JSON")
    p_parse.add_argument("input", help="Path to recipe text file")
    p_parse.add_argument("--out", default="output", help="Output directory (default: output/)")
    p_parse.set_defaults(func=cmd_parse)

    # run sub-command
    p_run = sub.add_parser("run", help="Run full enrichment pipeline")
    p_run.add_argument("input", help="Path to recipe text file")
    p_run.add_argument("--evidence", default="evidence", help="Evidence directory (default: evidence/)")
    p_run.add_argument("--out", default="output", help="Output directory (default: output/)")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
