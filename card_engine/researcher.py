from __future__ import annotations

import hashlib
import logging
import os
import pickle
import random
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    import requests
    from bs4 import BeautifulSoup
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False
    logger.warning("requests/beautifulsoup4 not available; researcher will return TODO results")

# ---------------------------------------------------------------------------
# Static UK ingredient data (Tesco / Sainsbury's typical prices, early 2025).
# Each entry: keyword → {low: £/100g, high: £/100g, kcal: kcal/100g}
# Keywords are matched case-insensitively as substrings of the cleaned
# ingredient name, checked in order — more specific entries first.
# ---------------------------------------------------------------------------
_STATIC_UK_DATA: list[tuple[str, dict]] = [
    # ── Meats ──────────────────────────────────────────────────────────────
    ("chicken thigh",       {"low": 0.38, "high": 0.55, "kcal": 177}),
    ("chicken breast",      {"low": 0.45, "high": 0.65, "kcal": 165}),
    ("chicken",             {"low": 0.38, "high": 0.55, "kcal": 165}),
    ("minced beef",         {"low": 0.55, "high": 0.80, "kcal": 225}),
    ("beef mince",          {"low": 0.55, "high": 0.80, "kcal": 225}),
    ("brisket",             {"low": 0.70, "high": 0.95, "kcal": 155}),
    ("pork shoulder",       {"low": 0.50, "high": 0.75, "kcal": 215}),
    ("pork ribs",           {"low": 0.55, "high": 0.80, "kcal": 240}),
    ("ribs",                {"low": 0.55, "high": 0.80, "kcal": 240}),
    ("veal knuckle",        {"low": 0.65, "high": 0.95, "kcal": 150}),
    ("pig trotter",         {"low": 0.30, "high": 0.50, "kcal": 185}),
    ("marrow bone",         {"low": 0.35, "high": 0.55, "kcal": 175}),
    ("chicken feet",        {"low": 0.20, "high": 0.40, "kcal": 215}),
    ("meat",                {"low": 0.45, "high": 0.80, "kcal": 180}),
    # ── Dairy & eggs ───────────────────────────────────────────────────────
    ("clarified butter",    {"low": 0.55, "high": 0.75, "kcal": 900}),
    ("beef dripping",       {"low": 0.30, "high": 0.50, "kcal": 900}),
    ("butter",              {"low": 0.45, "high": 0.65, "kcal": 717}),
    ("double cream",        {"low": 0.28, "high": 0.45, "kcal": 340}),
    ("cream",               {"low": 0.28, "high": 0.45, "kcal": 340}),
    ("milk",                {"low": 0.05, "high": 0.08, "kcal": 61}),
    ("cheddar",             {"low": 0.45, "high": 0.70, "kcal": 402}),
    ("grated cheese",       {"low": 0.45, "high": 0.70, "kcal": 402}),
    ("cheese",              {"low": 0.45, "high": 0.70, "kcal": 402}),
    ("egg yolk",            {"low": 0.55, "high": 0.75, "kcal": 322}),
    ("egg white",           {"low": 0.35, "high": 0.55, "kcal": 52}),
    ("egg",                 {"low": 0.35, "high": 0.55, "kcal": 143}),
    # ── Flours, grains, dry goods ───────────────────────────────────────────
    ("strong flour",        {"low": 0.08, "high": 0.12, "kcal": 341}),
    ("plain flour",         {"low": 0.07, "high": 0.11, "kcal": 341}),
    ("flour",               {"low": 0.07, "high": 0.12, "kcal": 341}),
    ("brown sugar",         {"low": 0.07, "high": 0.12, "kcal": 373}),
    ("sugar",               {"low": 0.06, "high": 0.10, "kcal": 387}),
    ("yeast",               {"low": 0.40, "high": 0.65, "kcal": 105}),
    ("pink curing salt",    {"low": 0.15, "high": 0.30, "kcal": 0}),
    ("salt",                {"low": 0.03, "high": 0.07, "kcal": 0}),
    # ── Oils & fats ────────────────────────────────────────────────────────
    ("olive oil",           {"low": 0.25, "high": 0.45, "kcal": 884}),
    ("neutral oil",         {"low": 0.10, "high": 0.18, "kcal": 900}),
    ("sunflower oil",       {"low": 0.10, "high": 0.18, "kcal": 900}),
    ("oil",                 {"low": 0.10, "high": 0.20, "kcal": 884}),
    # ── Vinegars, wines, acids ──────────────────────────────────────────────
    ("red wine vinegar",    {"low": 0.06, "high": 0.12, "kcal": 18}),
    ("white wine vinegar",  {"low": 0.06, "high": 0.12, "kcal": 18}),
    ("balsamic vinegar",    {"low": 0.15, "high": 0.30, "kcal": 88}),
    ("vinegar",             {"low": 0.05, "high": 0.10, "kcal": 18}),
    ("red wine",            {"low": 0.05, "high": 0.10, "kcal": 68}),
    ("white wine",          {"low": 0.05, "high": 0.10, "kcal": 77}),
    ("lime juice",          {"low": 0.12, "high": 0.22, "kcal": 25}),
    ("lemon juice",         {"low": 0.10, "high": 0.20, "kcal": 22}),
    ("citrus",              {"low": 0.12, "high": 0.22, "kcal": 25}),
    # ── Sauces, pastes, stocks ──────────────────────────────────────────────
    ("tomato purée",        {"low": 0.14, "high": 0.22, "kcal": 83}),
    ("tomato paste",        {"low": 0.14, "high": 0.22, "kcal": 83}),
    ("tomato puree",        {"low": 0.14, "high": 0.22, "kcal": 83}),
    ("soy sauce",           {"low": 0.10, "high": 0.18, "kcal": 53}),
    ("mustard",             {"low": 0.12, "high": 0.25, "kcal": 66}),
    ("honey",               {"low": 0.35, "high": 0.55, "kcal": 304}),
    ("syrup",               {"low": 0.20, "high": 0.40, "kcal": 280}),
    ("chicken stock",       {"low": 0.04, "high": 0.08, "kcal": 8}),
    ("fish stock",          {"low": 0.05, "high": 0.10, "kcal": 8}),
    ("brown stock",         {"low": 0.04, "high": 0.08, "kcal": 10}),
    ("stock",               {"low": 0.04, "high": 0.08, "kcal": 8}),
    # ── Spices & dried herbs ────────────────────────────────────────────────
    ("smoked paprika",      {"low": 0.55, "high": 0.85, "kcal": 282}),
    ("paprika",             {"low": 0.50, "high": 0.80, "kcal": 282}),
    ("black pepper",        {"low": 0.45, "high": 0.70, "kcal": 251}),
    ("pepper",              {"low": 0.45, "high": 0.70, "kcal": 251}),
    ("garlic powder",       {"low": 0.50, "high": 0.80, "kcal": 331}),
    ("onion powder",        {"low": 0.50, "high": 0.80, "kcal": 341}),
    ("chilli powder",       {"low": 0.50, "high": 0.80, "kcal": 282}),
    ("ground mustard",      {"low": 0.45, "high": 0.75, "kcal": 452}),
    ("mustard powder",      {"low": 0.45, "high": 0.75, "kcal": 452}),
    ("ground cumin",        {"low": 0.50, "high": 0.80, "kcal": 375}),
    ("cumin",               {"low": 0.50, "high": 0.80, "kcal": 375}),
    ("allspice",            {"low": 0.55, "high": 0.85, "kcal": 263}),
    ("thyme",               {"low": 0.40, "high": 0.65, "kcal": 101}),
    ("bay",                 {"low": 0.35, "high": 0.60, "kcal": 313}),
    ("nutmeg",              {"low": 0.60, "high": 0.95, "kcal": 525}),
    ("dried herbs",         {"low": 0.40, "high": 0.70, "kcal": 150}),
    ("herbs",               {"low": 0.35, "high": 0.65, "kcal": 150}),
    ("spices",              {"low": 0.45, "high": 0.75, "kcal": 200}),
    # ── Fresh produce ───────────────────────────────────────────────────────
    ("scotch bonnet",       {"low": 0.35, "high": 0.60, "kcal": 40}),
    ("red pepper",          {"low": 0.12, "high": 0.22, "kcal": 31}),
    ("chilli",              {"low": 0.20, "high": 0.35, "kcal": 40}),
    ("parsley",             {"low": 0.28, "high": 0.50, "kcal": 36}),
    ("parsley stalks",      {"low": 0.25, "high": 0.45, "kcal": 36}),
    ("shallot",             {"low": 0.20, "high": 0.35, "kcal": 72}),
    ("garlic",              {"low": 0.18, "high": 0.35, "kcal": 149}),
    ("onion",               {"low": 0.06, "high": 0.12, "kcal": 40}),
    ("carrot",              {"low": 0.06, "high": 0.12, "kcal": 41}),
    ("celery",              {"low": 0.08, "high": 0.15, "kcal": 16}),
    ("tomatoes",            {"low": 0.08, "high": 0.15, "kcal": 24}),
    ("tomato",              {"low": 0.08, "high": 0.15, "kcal": 24}),
    ("baby potatoes",       {"low": 0.08, "high": 0.14, "kcal": 77}),
    ("potatoes",            {"low": 0.07, "high": 0.12, "kcal": 77}),
    ("potato",              {"low": 0.07, "high": 0.12, "kcal": 77}),
    ("lime",                {"low": 0.18, "high": 0.30, "kcal": 30}),
    ("lemon",               {"low": 0.15, "high": 0.25, "kcal": 29}),
    # ── Chocolate & confectionery ───────────────────────────────────────────
    ("dark chocolate",      {"low": 0.55, "high": 0.90, "kcal": 546}),
    ("chocolate",           {"low": 0.50, "high": 0.85, "kcal": 530}),
    # ── Specialist / modernist hydrocolloids ───────────────────────────────
    ("agar",                {"low": 1.50, "high": 2.50, "kcal": 0}),
    ("gelatine",            {"low": 0.90, "high": 1.50, "kcal": 335}),
    ("gelatine leaf",       {"low": 0.90, "high": 1.50, "kcal": 335}),
    ("xanthan",             {"low": 1.80, "high": 3.00, "kcal": 0}),
    ("ultratex",            {"low": 2.20, "high": 3.50, "kcal": 0}),
    ("gellaspessa",         {"low": 2.00, "high": 3.50, "kcal": 0}),
    ("pectin",              {"low": 1.10, "high": 2.00, "kcal": 160}),
    ("lecithin",            {"low": 1.50, "high": 2.50, "kcal": 763}),
    # ── Water / wood chips (zero cost, zero kcal) ───────────────────────────
    ("cold water",          {"low": 0.00, "high": 0.00, "kcal": 0}),
    ("water",               {"low": 0.00, "high": 0.00, "kcal": 0}),
    ("wood chips",          {"low": 0.00, "high": 0.00, "kcal": 0}),
]

# Pre-compile lowercase keys for fast lookup
_STATIC_UK_DATA_LOWER: list[tuple[str, dict]] = [
    (kw.lower(), v) for kw, v in _STATIC_UK_DATA
]


def _clean_ingredient_text(raw: str) -> str:
    """Strip quantities, units, parenthetical notes, and punctuation from a
    raw ingredient line so keyword matching works cleanly."""
    # Remove quantity prefix: leading numbers, fractions (½ ¼ ¾ ⅔), units
    text = re.sub(
        r"^[\d½¼¾⅔⅓⅛\s]+(?:kg|g|ml|l|tsp|tbsp|cup|cups|pinch|dash|handful|bunch|cloves?|"
        r"sticks?|slices?|heads?|sprig|sprigs|packets?|litre|liter)s?\b[.,]?\s*",
        "", raw, flags=re.IGNORECASE,
    )
    # Remove parenthetical alternatives / notes like "(optional)" "(skin on)"
    text = re.sub(r"\(.*?\)", "", text)
    # Remove bullet characters and leading/trailing whitespace
    text = text.lstrip("•").strip(" ,.")
    return text.lower()


def _static_lookup(ingredient_raw: str) -> Optional[dict]:
    """Return static {low, high, kcal} data for an ingredient, or None."""
    cleaned = _clean_ingredient_text(ingredient_raw)
    for keyword, data in _STATIC_UK_DATA_LOWER:
        if keyword in cleaned:
            return data
    return None

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
]

COST_DOMAINS = [
    "tesco.com", "sainsburys.co.uk", "asda.com", "waitrose.com",
    "marksandspencer.com", "aldi.co.uk", "lidl.co.uk",
    "brakes.co.uk", "bidfood.co.uk", "booker.co.uk",
    "jjfoodservice.com", "regencyfoods.com", "costco.co.uk",
]
KCAL_DOMAINS = ["myfitnesspal.com", "cronometer.com", "fatsecret.co.uk"]
YIELD_DOMAINS = ["bbcgoodfood.com", "allrecipes.com", "foodnetwork.com"]

SITE_SEARCH_URLS = {
    "tesco.com": "https://www.tesco.com/groceries/en-GB/search?query={q}",
    "sainsburys.co.uk": "https://www.sainsburys.co.uk/gol-ui/SearchDisplayView?filters[keyword]={q}",
    "asda.com": "https://groceries.asda.com/search/{q}",
}


@dataclass
class ResearchResult:
    ingredient_name: str
    cost_low_avg: float
    cost_high_avg: float
    kcal_per_100g: float
    cost_notes: str
    kcal_notes: str
    blocked_sources: list[str] = field(default_factory=list)
    todo: bool = False


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16] + ".pkl"


def _load_cache(cache_dir: str, url: str):
    key = _cache_key(url)
    path = Path(cache_dir) / key
    if path.exists():
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return None


def _save_cache(cache_dir: str, url: str, data) -> None:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    key = _cache_key(url)
    path = Path(cache_dir) / key
    try:
        with open(path, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        logger.warning("Cache write failed for %s: %s", url, e)


def _can_fetch(url: str) -> bool:
    """Check robots.txt for url."""
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch("*", url)
    except Exception:
        return True  # assume allowed on error


def _fetch_url(url: str, cache_dir: str, session=None) -> Optional[str]:
    """Fetch URL with caching and rate limiting. Returns HTML or None."""
    cached = _load_cache(cache_dir, url)
    if cached is not None:
        logger.debug("Cache hit: %s", url)
        return cached

    if not _REQUESTS_AVAILABLE:
        return None

    time.sleep(random.uniform(0.5, 2.5))

    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        sess = session or requests.Session()
        resp = sess.get(url, headers=headers, timeout=10, allow_redirects=True)
        if resp.status_code == 403:
            logger.warning("403 blocked: %s", url)
            return None
        if resp.status_code != 200:
            logger.warning("HTTP %d for %s", resp.status_code, url)
            return None
        html = resp.text
        _save_cache(cache_dir, url, html)
        return html
    except Exception as e:
        logger.warning("Fetch error for %s: %s", url, e)
        return None


def _extract_prices(html: str) -> list[float]:
    """Extract GBP prices from HTML."""
    prices = re.findall(r"£\s*(\d+\.\d{2})", html)
    return [float(p) for p in prices]


def _extract_pack_size_g(html: str) -> Optional[float]:
    """Extract pack size in grams from HTML."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|ml|l)\b", html, re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "kg":
        return val * 1000
    elif unit == "g":
        return val
    elif unit == "l":
        return val * 1000
    elif unit == "ml":
        return val
    return None


def _extract_kcal_per_100g(html: str) -> Optional[float]:
    """Extract kcal per 100g from nutrition table."""
    patterns = [
        r"(\d+)\s*kcal.*?per\s*100\s*g",
        r"per\s*100\s*g.*?(\d+)\s*kcal",
        r"calories.*?(\d+).*?100g",
        r"energy.*?(\d+)\s*kcal",
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            val = float(m.group(1))
            if 1 < val < 1000:
                return val
    return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _research_cost(ingredient: str, cache_dir: str) -> tuple[list[dict], list[str]]:
    """Research cost from grocery sites. Returns (candidates, blocked_sources)."""
    candidates: list[dict] = []
    blocked: list[str] = []
    q = ingredient.replace(" ", "+")

    if not _REQUESTS_AVAILABLE:
        return candidates, blocked

    session = requests.Session() if _REQUESTS_AVAILABLE else None

    for domain, url_template in SITE_SEARCH_URLS.items():
        url = url_template.format(q=q)
        try:
            if not _can_fetch(url):
                logger.info("robots.txt disallows: %s", url)
                blocked.append(domain)
                continue

            html = _fetch_url(url, cache_dir, session)
            if html is None:
                blocked.append(domain)
                continue

            prices = _extract_prices(html)
            size_g = _extract_pack_size_g(html)
            if prices and size_g and size_g > 0:
                for price in prices[:3]:
                    unit_price = price / size_g
                    candidates.append({"unit_price_per_g": unit_price, "source": domain})
        except Exception as e:
            logger.warning("Cost research error for %s on %s: %s", ingredient, domain, e)
            blocked.append(domain)

    # Check evidence dir
    evidence_dir = Path(cache_dir) / "evidence"
    slug = _slug(ingredient)
    for domain in COST_DOMAINS:
        evidence_path = evidence_dir / f"{slug}_{domain}.html"
        if evidence_path.exists():
            try:
                html = evidence_path.read_text(encoding="utf-8", errors="replace")
                prices = _extract_prices(html)
                size_g = _extract_pack_size_g(html)
                if prices and size_g and size_g > 0:
                    for price in prices[:3]:
                        unit_price = price / size_g
                        candidates.append({"unit_price_per_g": unit_price, "source": f"{domain} (evidence)"})
            except Exception as e:
                logger.warning("Evidence file error: %s", e)

    return candidates, blocked


def _research_kcal(ingredient: str, cache_dir: str) -> tuple[Optional[float], list[str]]:
    """Research kcal per 100g from nutrition sites. Returns (kcal_per_100g, blocked)."""
    blocked: list[str] = []

    if not _REQUESTS_AVAILABLE:
        return None, blocked

    session = requests.Session()
    q = ingredient.replace(" ", "+")

    for domain in KCAL_DOMAINS:
        url = f"https://www.bing.com/search?q={q}+site:{domain}"
        try:
            html = _fetch_url(url, cache_dir, session)
            if html is None:
                blocked.append(domain)
                continue

            soup = BeautifulSoup(html, "lxml")
            links = [a.get("href", "") for a in soup.find_all("a", href=True)]
            target_links = [l for l in links if domain in l and l.startswith("http")]

            for link in target_links[:2]:
                page_html = _fetch_url(link, cache_dir, session)
                if page_html:
                    kcal = _extract_kcal_per_100g(page_html)
                    if kcal:
                        return kcal, blocked

        except Exception as e:
            logger.warning("Kcal research error for %s on %s: %s", ingredient, domain, e)
            blocked.append(domain)

    return None, blocked


def compute_cost_range(candidates: list[dict]) -> dict:
    """
    candidates: list of {unit_price_per_g: float, source: str}
    Returns {low_avg: float, high_avg: float, notes: str}
    using half-split mean (same algorithm as calculator.half_split_mean, inlined here
    to avoid a circular import between researcher and calculator).
    """
    if not candidates:
        return {"low_avg": 0.0, "high_avg": 0.0, "notes": "no data"}

    prices = sorted(c["unit_price_per_g"] for c in candidates)
    import math
    half = math.ceil(len(prices) / 2)
    low_avg = sum(prices[:half]) / half
    high_avg = sum(prices[-half:]) / half
    sources = list({c["source"] for c in candidates})
    return {
        "low_avg": low_avg,
        "high_avg": high_avg,
        "notes": f"Sources: {', '.join(sources)}",
    }


def research_ingredients(ingredients: list[str], cache_dir: str = "cache") -> list[ResearchResult]:
    """Research all ingredients.

    Lookup order:
    1. Live scraping (Tesco / Sainsbury's / ASDA search pages).
    2. Pre-built bing HTML evidence files in cache/evidence/.
    3. Static UK supermarket data table (embedded, used when live sources are
       unavailable or blocked — e.g. in CI / offline environments).
    """
    results = []
    for ing in ingredients:
        logger.info("Researching ingredient: %s", ing)
        try:
            cost_candidates, cost_blocked = _research_cost(ing, cache_dir)
            cost_range = compute_cost_range(cost_candidates)

            kcal, kcal_blocked = _research_kcal(ing, cache_dir)
            blocked = list(set(cost_blocked + kcal_blocked))

            # ── Static fallback ──────────────────────────────────────────
            static = _static_lookup(ing)
            used_static = False
            if static is not None:
                if not cost_candidates:
                    # Convert £/100g to £/g so units match the rest of the system
                    cost_range = {
                        "low_avg": static["low"] / 100,
                        "high_avg": static["high"] / 100,
                        "notes": "static UK supermarket data (Tesco/Sainsbury's typical, early 2025)",
                    }
                    used_static = True
                if kcal is None:
                    kcal = static["kcal"] or None
                    used_static = True

            todo = cost_range["low_avg"] == 0.0 and kcal is None

            result = ResearchResult(
                ingredient_name=ing,
                cost_low_avg=cost_range["low_avg"],
                cost_high_avg=cost_range["high_avg"],
                kcal_per_100g=kcal or 0.0,
                cost_notes=cost_range["notes"],
                kcal_notes=(
                    "kcal/100g from nutrition sites" if (kcal and not used_static)
                    else ("kcal/100g from static UK data table" if (kcal and used_static)
                          else "kcal not found")
                ),
                blocked_sources=blocked,
                todo=todo,
            )
        except Exception as e:
            logger.error("Research failed for %s: %s", ing, e)
            result = ResearchResult(
                ingredient_name=ing,
                cost_low_avg=0.0,
                cost_high_avg=0.0,
                kcal_per_100g=0.0,
                cost_notes="research error",
                kcal_notes="research error",
                blocked_sources=[],
                todo=True,
            )
        results.append(result)

    return results
