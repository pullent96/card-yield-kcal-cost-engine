# Card Yield Kcal Cost Engine

A Python pipeline for parsing recipe text files, researching ingredient costs and kcal values, and rendering professional recipe cards as `.docx` files.

## Installation

```bash
pip install -r requirements.txt
```

Or install as a package:

```bash
pip install -e .
```

## CLI Usage

### Parse recipes to JSON

```bash
python -m card_engine parse recipes/ --out output/parsed
```

Reads all `.txt` files from `recipes/`, deduplicates, and writes one JSON per recipe.

### Full pipeline (parse + research + render)

```bash
python -m card_engine run recipes/ --out output/rendered --portions 10
```

Runs the complete pipeline: parse -> web research -> compute metrics -> render `.docx`.

### Render from JSON (no research)

```bash
python -m card_engine render output/parsed/ --out output/rendered --portions 10
```

Renders `.docx` files from previously parsed JSON, skipping web research.

## Folder Layout

```
card_engine/
  __init__.py       # package init
  models.py         # Ingredient, RecipeCard, RecipeParsed dataclasses
  parser.py         # .txt recipe parser
  researcher.py     # web scraper for cost/kcal data
  calculator.py     # metric computation
  renderer.py       # python-docx renderer
  cli.py            # argparse CLI
  __main__.py       # python -m card_engine entrypoint
recipes/
  example_chicken_traybake.txt
  raw_dump.txt      # optional: many recipes concatenated
examples/
  sample_card.json  # example parsed recipe
tests/
  test_calculator.py
  test_parser.py
  test_renderer.py
cache/              # auto-created; stores HTTP response cache
output/             # auto-created; stores rendered files
```

## Recipe File Format

Each `.txt` file contains one recipe:

```
Recipe Title

BASE
* ingredient 1
* ingredient 2

METHOD
1. Step one.
2. Step two.

TOTAL TIME
45 minutes

NOTES
Any additional notes.
```

Multiple recipes can be stored in a single file (e.g. `raw_dump.txt`) separated by **two or more blank lines**.

## How Cost Range Works

Costs are estimated using a **half-split mean**:

1. All unit prices (GBP/g) found across grocery sites are sorted ascending.
2. The **lower half** (first ceil(n/2) values) gives `low_avg`.
3. The **upper half** (last ceil(n/2) values) gives `high_avg`.
4. For odd numbers of values, the middle value contributes to both halves.

This gives a stable low-high range that resists outlier distortion.

## Scraping Reliability Caveats

- Grocery sites frequently block automated requests (HTTP 403, CAPTCHA).
- Responses are cached in `cache/` (pickle files keyed by URL SHA-256 hash).
- Requests are rate-limited with a randomized 0.5-2.5s delay.
- `robots.txt` is respected for all domains.
- If a site blocks all requests, that ingredient will be marked **TODO** in the output.

## TODO Placeholder Behaviour

When research fails entirely for an ingredient, the rendered card will show:

```
TODO: [kcal could not be researched -- no data]
TODO: [cost could not be researched -- no data]
```

This makes it easy to identify which values need manual verification.

## Running Tests

```bash
python -m pytest tests/ -v
```

or

```bash
python -m unittest discover -s tests
```
