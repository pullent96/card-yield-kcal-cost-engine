from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from card_engine.models import RecipeParsed
from card_engine.researcher import ResearchResult

logger = logging.getLogger(__name__)

try:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False
    logger.warning("python-docx not available; renderer will be limited")


def _add_bold_heading(doc, text: str, level: int = 2) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(13 if level == 1 else 11)


def render_recipe_docx(
    recipe: RecipeParsed,
    metrics: Optional[dict],
    research: list[ResearchResult],
    output_path: str,
    target_portions: int = 10,
) -> None:
    """Create a .docx file for a single recipe."""
    if not _DOCX_AVAILABLE:
        raise RuntimeError("python-docx is not installed")

    doc = Document()

    # RECIPE CARD heading
    title_heading = doc.add_heading("RECIPE CARD", level=1)
    title_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Title
    _add_bold_heading(doc, "Title")
    doc.add_paragraph(recipe.title)

    # Yield
    _add_bold_heading(doc, "Yield")
    total_g = 0.0
    _weight_re = re.compile(r"(\d+(?:\.\d+)?)\s*(g|kg)\b", re.IGNORECASE)
    for ing in recipe.ingredients_raw:
        m = _weight_re.search(ing)
        if m:
            val = float(m.group(1))
            if m.group(2).lower() == "kg":
                val *= 1000
            total_g += val

    if total_g > 0:
        per_portion = total_g / target_portions
        yield_text = f"~{target_portions} portions | {total_g:.0f}g total | {per_portion:.0f}g per portion"
    else:
        yield_text = f"~{target_portions} portions | [total weight unknown] | [per portion unknown]"
    doc.add_paragraph(yield_text)

    # INGREDIENTS
    _add_bold_heading(doc, "INGREDIENTS")
    for ing in recipe.ingredients_raw:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(ing)

    # METHOD
    _add_bold_heading(doc, "METHOD")
    for i, step in enumerate(recipe.method_raw, 1):
        p = doc.add_paragraph(style="List Number")
        p.add_run(step)

    # TOTAL TIME
    _add_bold_heading(doc, "TOTAL TIME")
    doc.add_paragraph(recipe.total_time or "[unknown]")

    # KCAL
    _add_bold_heading(doc, "KCAL")
    kcal_result = next((r for r in research if not r.todo and r.kcal_per_100g > 0), None)
    if metrics and metrics.get("kcal_per_serving", 0) > 0:
        kcal_text = f"{metrics['kcal_per_serving']:.0f} kcal per portion (estimated)"
    elif kcal_result:
        kcal_text = f"{kcal_result.kcal_per_100g:.0f} kcal per 100g (estimated)"
    else:
        todo_note = ""
        if research:
            todo_note = research[0].kcal_notes
        kcal_text = f"TODO: [kcal could not be researched — {todo_note or 'no data'}]"
    doc.add_paragraph(kcal_text)

    # APPROXIMATE COST IN UK TODAY
    _add_bold_heading(doc, "APPROXIMATE COST IN UK TODAY")
    cost_results = [r for r in research if not r.todo and (r.cost_low_avg > 0 or r.cost_high_avg > 0)]
    if metrics and metrics.get("total_cost", 0) > 0:
        total = metrics["total_cost"]
        cost_text = f"£{total:.2f} total | £{metrics['cost_per_serving']:.2f} per portion (estimated)"
    elif cost_results:
        low = sum(r.cost_low_avg for r in cost_results)
        high = sum(r.cost_high_avg for r in cost_results)
        cost_text = f"£{low:.2f}–£{high:.2f} (estimated range)"
    else:
        todo_note = ""
        if research:
            todo_note = research[0].cost_notes
        cost_text = f"TODO: [cost could not be researched — {todo_note or 'no data'}]"
    doc.add_paragraph(cost_text)

    # FINISH
    _add_bold_heading(doc, "FINISH")
    finish_notes = ""
    m = re.search(r"\[FINISH:\s*([^\]]+)\]", recipe.notes or "")
    if m:
        finish_notes = m.group(1)
    doc.add_paragraph(finish_notes or "[see method]")

    # NOTES
    _add_bold_heading(doc, "NOTES")
    notes_parts = []
    if recipe.notes:
        clean_notes = re.sub(r"\[[A-Z ]+:\s*[^\]]+\]", "", recipe.notes).strip()
        if clean_notes:
            notes_parts.append(clean_notes)
    for r in research:
        if r.blocked_sources:
            notes_parts.append(f"Blocked sources for {r.ingredient_name}: {', '.join(r.blocked_sources)}")
        if r.todo:
            notes_parts.append(f"Research TODO: {r.ingredient_name} — {r.cost_notes}")
    doc.add_paragraph("\n".join(notes_parts) if notes_parts else "[none]")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    logger.info("Saved recipe docx: %s", output_path)
