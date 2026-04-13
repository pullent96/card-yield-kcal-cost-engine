# Card Yield Kcal Cost Engine

A Python recipe card engine that parses raw recipe text, enriches it with cost, calorie (kcal) and yield data from retailer evidence URLs, renders a structured JSON recipe card, and exports each recipe to its own `.docx` file.

## Requirements

- Python 3.10+
- `requests`, `beautifulsoup4`, `lxml`, `python-docx`

Install everything with:

```bash
pip install -e .
```

## Folder Structure

```
card_engine/            # main package
  models.py             # data models
  parser.py             # recipe text → ParsedRecipe
  enrichment/
    cost_engine.py      # cost from retailer URLs
    kcal_engine.py      # kcal from nutrition URLs
    yield_engine.py     # yield / portions heuristics
  providers/
    base.py             # Sainsbury's, ASDA, Tesco extractors + dispatcher
  renderer.py           # assemble final RecipeCard
  exporter.py           # export RecipeCard → .docx
  cli.py                # CLI entrypoint
  calculator.py         # backward-compatible cost/kcal totals
recipes/                # raw recipe .txt files
evidence/
  cost/<slug>.json      # ingredient key → list of retailer product URLs
  kcal/<slug>.json      # ingredient key → list of nutrition/product URLs
  yield/<slug>.json     # list of yield URLs (may be empty)
output/                 # generated .recipe-card.json and .docx files
tests/
  fixtures/             # sample HTML pages (no live HTTP in tests)
```

## Evidence JSON Format

### `evidence/cost/<slug>.json`
```json
{
  "beef_mince": [
    "https://www.sainsburys.co.uk/gol-ui/product/beef-mince-500g",
    "https://www.tesco.com/groceries/beef-mince-500g"
  ],
  "tin_chopped_tomatoes": [
    "https://www.asda.com/product/chopped-tomatoes-400g"
  ]
}
```

### `evidence/kcal/<slug>.json`
```json
{
  "beef_mince": [
    "https://www.sainsburys.co.uk/gol-ui/product/beef-mince-500g"
  ]
}
```

### `evidence/yield/<slug>.json`
```json
["https://www.bbcgoodfood.com/recipes/chilli-con-carne"]
```
An empty array `[]` triggers the ingredient-weight heuristic (default 10 portions).

## CLI

### Parse a recipe to JSON

```bash
recipe-engine parse recipes/chilli-con-carne.txt --out output/
```

Produces `output/chilli-con-carne.parsed.json`.

### Run the full enrichment pipeline

```bash
recipe-engine run recipes/chilli-con-carne.txt --evidence evidence/ --out output/
```

Produces:
- `output/chilli-con-carne.recipe-card.json`
- `output/chilli-con-carne.docx`  ← **one `.docx` per recipe**

## Chilli Con Carne Example Workflow

1. Place the recipe text at `recipes/chilli-con-carne.txt` (already included).

2. Populate evidence URLs in:
   - `evidence/cost/chilli-con-carne.json`
   - `evidence/kcal/chilli-con-carne.json`
   - `evidence/yield/chilli-con-carne.json`

3. Run:

```bash
recipe-engine run recipes/chilli-con-carne.txt --evidence evidence/ --out output/
```

4. Open `output/chilli-con-carne.docx` for the formatted recipe card.

## Recipe Text Format

```
TITLE: Chilli Con Carne

BASE:
- 500g beef mince
- 400g tin chopped tomatoes
- 1 tbsp chilli powder

METHOD:
1. Brown the mince.
2. Add tomatoes and spices.
3. Simmer 30 minutes.

NOTES:
- Can be frozen for 3 months.
```

Sections: `TITLE:`, `BASE:` (or `INGREDIENTS:`), `METHOD:` (or `STEPS:`), `NOTES:`.

## Tests

```bash
python -m pytest tests/ -v
```

Tests cover: parsing, normalisation, low/mid/high aggregation, provider extraction (fixture-based, no live HTTP), DOCX generation.

## Library Usage

```python
from card_engine import parse_recipe_text, render_recipe_card, export_docx
from card_engine.enrichment import run_cost_engine, run_kcal_engine, run_yield_engine

recipe = parse_recipe_text(open("recipes/chilli-con-carne.txt").read())
cost_results  = run_cost_engine(recipe.ingredients, cost_evidence)
kcal_results  = run_kcal_engine(recipe.ingredients, kcal_evidence)
yield_result  = run_yield_engine(recipe.ingredients, yield_urls)
card = render_recipe_card(recipe, cost_results, kcal_results, yield_result)
docx_path = export_docx(card, "output/")
```

