import unittest
import textwrap
from pathlib import Path

from card_engine.parser import parse_file, parse_directory, _compute_hash


class TestParseFile(unittest.TestCase):

    def _tmpdir(self):
        d = Path(__file__).parent.parent / "test_tmp"
        d.mkdir(exist_ok=True)
        return d

    def _write_temp(self, content: str, suffix=".txt") -> str:
        tmpdir = self._tmpdir()
        path = tmpdir / f"test_{hash(content) & 0xFFFFFFFF}{suffix}"
        path.write_text(content, encoding="utf-8")
        return str(path)

    def tearDown(self):
        tmpdir = Path(__file__).parent.parent / "test_tmp"
        if tmpdir.exists():
            for f in tmpdir.glob("*"):
                f.unlink()
            try:
                tmpdir.rmdir()
            except OSError:
                pass

    def test_parse_single_recipe(self):
        content = textwrap.dedent("""\
            Tomato Soup

            BASE
            \u2022 500g tomatoes
            \u2022 1 onion

            METHOD
            1. Blend tomatoes and onion.
            2. Heat and serve.

            TOTAL TIME
            30 minutes
        """)
        path = self._write_temp(content)
        results = parse_file(path)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r.title, "Tomato Soup")
        self.assertEqual(r.total_time, "30 minutes")

    def test_parse_bullet_ingredients(self):
        content = textwrap.dedent("""\
            Pasta Dish

            INGREDIENTS
            \u2022 200g pasta
            \u2022 100g cheese

            METHOD
            Cook pasta.
        """)
        path = self._write_temp(content)
        results = parse_file(path)
        self.assertEqual(len(results), 1)
        self.assertIn("200g pasta", results[0].ingredients_raw)
        self.assertIn("100g cheese", results[0].ingredients_raw)

    def test_parse_multi_recipe_dump(self):
        content = textwrap.dedent("""\
            First Recipe

            BASE
            \u2022 100g flour

            METHOD
            Mix and bake.



            Second Recipe

            BASE
            \u2022 200g sugar

            METHOD
            Dissolve sugar.
        """)
        path = self._write_temp(content, suffix="_raw_dump.txt")
        results = parse_file(path)
        self.assertGreaterEqual(len(results), 2)
        titles = [r.title for r in results]
        self.assertIn("First Recipe", titles)
        self.assertIn("Second Recipe", titles)

    def test_dedupe_identical_recipes(self):
        content = textwrap.dedent("""\
            Garlic Bread

            BASE
            \u2022 1 baguette
            \u2022 2 tbsp butter

            METHOD
            Spread butter, bake 10 mins.
        """)
        tmpdir = self._tmpdir()
        for i in range(2):
            path = tmpdir / f"recipe_{i}.txt"
            path.write_text(content, encoding="utf-8")
        results = parse_directory(str(tmpdir), dedupe=True)
        garlic = [r for r in results if r.title == "Garlic Bread"]
        self.assertEqual(len(garlic), 1)

    def test_no_dedupe_identical_recipes(self):
        content = textwrap.dedent("""\
            Garlic Bread

            BASE
            \u2022 1 baguette
            \u2022 2 tbsp butter

            METHOD
            Spread butter, bake 10 mins.
        """)
        tmpdir = self._tmpdir()
        for i in range(2):
            path = tmpdir / f"recipe_{i}.txt"
            path.write_text(content, encoding="utf-8")
        results = parse_directory(str(tmpdir), dedupe=False)
        garlic = [r for r in results if r.title == "Garlic Bread"]
        self.assertEqual(len(garlic), 2)

    def test_compute_hash_consistent(self):
        h1 = _compute_hash("Test", ["ing1", "ing2"], ["step1"])
        h2 = _compute_hash("Test", ["ing1", "ing2"], ["step1"])
        self.assertEqual(h1, h2)

    def test_compute_hash_differs_on_change(self):
        h1 = _compute_hash("Test", ["ing1"], ["step1"])
        h2 = _compute_hash("Test", ["ing2"], ["step1"])
        self.assertNotEqual(h1, h2)
