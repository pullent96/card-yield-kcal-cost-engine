from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _recipe_parsed_to_dict(recipe) -> dict:
    return {
        "title": recipe.title,
        "ingredients_raw": recipe.ingredients_raw,
        "method_raw": recipe.method_raw,
        "total_time": recipe.total_time,
        "notes": recipe.notes,
        "source_file": recipe.source_file,
        "content_hash": recipe.content_hash,
    }


def _recipe_from_dict(d: dict):
    from card_engine.models import RecipeParsed
    return RecipeParsed(
        title=d.get("title", ""),
        ingredients_raw=d.get("ingredients_raw", []),
        method_raw=d.get("method_raw", []),
        total_time=d.get("total_time", ""),
        notes=d.get("notes", ""),
        source_file=d.get("source_file", ""),
        content_hash=d.get("content_hash", ""),
    )


def _safe_filename(title: str) -> str:
    return re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")[:60]


def cmd_parse(args) -> None:
    from card_engine.parser import parse_directory
    dedupe = not args.no_dedupe
    recipes = parse_directory(args.recipes_dir, dedupe=dedupe)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for recipe in recipes:
        filename = _safe_filename(recipe.title) + ".json"
        out_path = out_dir / filename
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(_recipe_parsed_to_dict(recipe), f, indent=2, ensure_ascii=False)
        print(f"Wrote: {out_path}")

    print(f"\nParsed {len(recipes)} recipe(s) to {out_dir}")


def cmd_run(args) -> None:
    from card_engine.parser import parse_directory
    from card_engine.researcher import research_ingredients
    from card_engine.renderer import render_recipe_docx

    dedupe = not args.no_dedupe
    recipes = parse_directory(args.recipes_dir, dedupe=dedupe)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for recipe in recipes:
        logger.info("Processing: %s", recipe.title)
        research = research_ingredients(recipe.ingredients_raw)
        filename = _safe_filename(recipe.title) + ".docx"
        out_path = str(out_dir / filename)
        try:
            render_recipe_docx(
                recipe=recipe,
                metrics=None,
                research=research,
                output_path=out_path,
                target_portions=args.portions,
            )
            print(f"Rendered: {out_path}")
        except Exception as e:
            logger.error("Render failed for %s: %s", recipe.title, e)

    print(f"\nProcessed {len(recipes)} recipe(s) to {out_dir}")


def cmd_render(args) -> None:
    from card_engine.renderer import render_recipe_docx

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    src = Path(args.json_file_or_dir)
    if src.is_dir():
        json_files = list(src.glob("*.json"))
    else:
        json_files = [src]

    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("Failed to load %s: %s", jf, e)
            continue

        recipe = _recipe_from_dict(data)
        filename = _safe_filename(recipe.title) + ".docx"
        out_path = str(out_dir / filename)
        try:
            render_recipe_docx(
                recipe=recipe,
                metrics=None,
                research=[],
                output_path=out_path,
                target_portions=args.portions,
            )
            print(f"Rendered: {out_path}")
        except Exception as e:
            logger.error("Render failed for %s: %s", recipe.title, e)

    print(f"\nRendered {len(json_files)} recipe(s) to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="card_engine",
        description="Recipe card yield/kcal/cost engine",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # parse subcommand
    p_parse = subparsers.add_parser("parse", help="Parse recipe .txt files to JSON")
    p_parse.add_argument("recipes_dir", help="Directory containing .txt recipe files")
    p_parse.add_argument("--out", default="output/parsed", help="Output directory for JSON files")
    p_parse.add_argument("--no-dedupe", action="store_true", help="Disable deduplication")
    p_parse.set_defaults(func=cmd_parse)

    # run subcommand
    p_run = subparsers.add_parser("run", help="Parse, research, compute, and render docx")
    p_run.add_argument("recipes_dir", help="Directory containing .txt recipe files")
    p_run.add_argument("--out", default="output/rendered", help="Output directory for .docx files")
    p_run.add_argument("--portions", type=int, default=10, help="Target number of portions")
    p_run.add_argument("--no-dedupe", action="store_true", help="Disable deduplication")
    p_run.set_defaults(func=cmd_run)

    # render subcommand
    p_render = subparsers.add_parser("render", help="Render docx from JSON without research")
    p_render.add_argument("json_file_or_dir", help="JSON file or directory of JSON files")
    p_render.add_argument("--out", default="output/rendered", help="Output directory for .docx files")
    p_render.add_argument("--portions", type=int, default=10, help="Target number of portions")
    p_render.set_defaults(func=cmd_render)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
