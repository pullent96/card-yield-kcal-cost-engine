"""Base provider interface and URL dispatcher."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ProviderResult:
    url: str
    price_gbp: Optional[float] = None          # shelf price
    pack_size_g: Optional[float] = None         # pack size in g or ml
    cost_per_100g: Optional[float] = None       # derived: price / (pack_size_g / 100)
    kcal_per_100g: Optional[float] = None       # from nutrition panel
    provider: str = "unknown"
    raw_meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# HTTP helper (injectable for testing)
# ---------------------------------------------------------------------------

def _default_fetch(url: str) -> str:
    resp = requests.get(url, timeout=15, headers={"User-Agent": "RecipeEngine/1.0"})
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# JSON-LD helpers (common across retailers)
# ---------------------------------------------------------------------------

def _extract_jsonld_products(soup: BeautifulSoup) -> list[dict]:
    """Return all JSON-LD Product objects found in the page."""
    results = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]
        else:
            continue
        for item in items:
            if isinstance(item, dict) and item.get("@type") in ("Product", "FoodProduct"):
                results.append(item)
            # Some pages wrap in @graph
            for sub in item.get("@graph", []):
                if isinstance(sub, dict) and sub.get("@type") in ("Product", "FoodProduct"):
                    results.append(sub)
    return results


def _parse_price(text: str) -> Optional[float]:
    """Extract first numeric price from a string."""
    m = re.search(r"[\d]+\.?\d*", text.replace(",", ""))
    return float(m.group()) if m else None


def _parse_weight_g(text: str) -> Optional[float]:
    """Parse a weight/volume like '400g', '1kg', '500ml', '1l' -> grams/ml."""
    text = text.lower().strip()
    m = re.search(r"([\d.]+)\s*(kg|g|ml|l)\b", text)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    multipliers = {"kg": 1000.0, "g": 1.0, "l": 1000.0, "ml": 1.0}
    return val * multipliers[unit]


# ---------------------------------------------------------------------------
# Sainsbury's provider
# ---------------------------------------------------------------------------

def _parse_sainsburys(soup: BeautifulSoup, url: str) -> ProviderResult:
    result = ProviderResult(url=url, provider="sainsburys")

    # Try JSON-LD first
    products = _extract_jsonld_products(soup)
    if products:
        p = products[0]
        offers = p.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price_str = offers.get("price", "")
        if price_str:
            result.price_gbp = _parse_price(str(price_str))
        weight_str = p.get("weight", "") or p.get("netContent", "")
        if weight_str:
            result.pack_size_g = _parse_weight_g(str(weight_str))
        # Nutrition
        nutrition = p.get("nutrition", {})
        if isinstance(nutrition, dict):
            energy = nutrition.get("calories", "") or nutrition.get("energyContent", "")
            if energy:
                result.kcal_per_100g = _parse_price(str(energy))

    # HTML fallback: price
    if result.price_gbp is None:
        price_tag = soup.select_one("[class*='pricePerUnit'], [class*='price']")
        if price_tag:
            result.price_gbp = _parse_price(price_tag.get_text())

    # HTML fallback: pack weight from page title or product name
    if result.pack_size_g is None:
        title_tag = soup.find("h1")
        if title_tag:
            result.pack_size_g = _parse_weight_g(title_tag.get_text())

    # Nutrition table fallback
    if result.kcal_per_100g is None:
        for row in soup.select("table tr, [class*='nutrition'] tr"):
            cells = row.find_all(["td", "th"])
            texts = [c.get_text(strip=True).lower() for c in cells]
            if texts and ("energy" in texts[0] or "kcal" in texts[0]):
                for cell_text in texts[1:]:
                    val = _parse_price(cell_text)
                    if val:
                        result.kcal_per_100g = val
                        break

    if result.price_gbp and result.pack_size_g:
        result.cost_per_100g = result.price_gbp / (result.pack_size_g / 100.0)

    return result


# ---------------------------------------------------------------------------
# ASDA provider
# ---------------------------------------------------------------------------

def _parse_asda(soup: BeautifulSoup, url: str) -> ProviderResult:
    result = ProviderResult(url=url, provider="asda")

    products = _extract_jsonld_products(soup)
    if products:
        p = products[0]
        offers = p.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price_str = offers.get("price", "")
        if price_str:
            result.price_gbp = _parse_price(str(price_str))

    if result.price_gbp is None:
        price_tag = soup.select_one("[class*='co-product__price'], [class*='price-current']")
        if price_tag:
            result.price_gbp = _parse_price(price_tag.get_text())

    if result.pack_size_g is None:
        h1 = soup.find("h1")
        if h1:
            result.pack_size_g = _parse_weight_g(h1.get_text())

    # Nutrition table
    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(strip=True).lower() for c in cells]
        if texts and ("energy" in texts[0] or "kcal" in texts[0]):
            for cell_text in texts[1:]:
                val = _parse_price(cell_text)
                if val and result.kcal_per_100g is None:
                    result.kcal_per_100g = val

    if result.price_gbp and result.pack_size_g:
        result.cost_per_100g = result.price_gbp / (result.pack_size_g / 100.0)

    return result


# ---------------------------------------------------------------------------
# Tesco provider
# ---------------------------------------------------------------------------

def _parse_tesco(soup: BeautifulSoup, url: str) -> ProviderResult:
    result = ProviderResult(url=url, provider="tesco")

    products = _extract_jsonld_products(soup)
    if products:
        p = products[0]
        offers = p.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price_str = offers.get("price", "")
        if price_str:
            result.price_gbp = _parse_price(str(price_str))
        weight_str = p.get("weight", "") or p.get("netContent", "")
        if weight_str:
            result.pack_size_g = _parse_weight_g(str(weight_str))

    if result.price_gbp is None:
        price_tag = soup.select_one("[class*='price-per-sellable-unit'], [class*='price']")
        if price_tag:
            result.price_gbp = _parse_price(price_tag.get_text())

    if result.pack_size_g is None:
        h1 = soup.find("h1")
        if h1:
            result.pack_size_g = _parse_weight_g(h1.get_text())

    # Nutrition
    for row in soup.select("table tr, [class*='nutrition-table'] tr"):
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(strip=True).lower() for c in cells]
        if texts and ("energy" in texts[0] or "kcal" in texts[0]):
            for cell_text in texts[1:]:
                val = _parse_price(cell_text)
                if val and result.kcal_per_100g is None:
                    result.kcal_per_100g = val

    if result.price_gbp and result.pack_size_g:
        result.cost_per_100g = result.price_gbp / (result.pack_size_g / 100.0)

    return result


# ---------------------------------------------------------------------------
# Generic / fallback provider
# ---------------------------------------------------------------------------

def _parse_generic(soup: BeautifulSoup, url: str) -> ProviderResult:
    result = ProviderResult(url=url, provider="generic")

    products = _extract_jsonld_products(soup)
    if products:
        p = products[0]
        offers = p.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price_str = offers.get("price", "")
        if price_str:
            result.price_gbp = _parse_price(str(price_str))

    if result.pack_size_g is None:
        h1 = soup.find("h1")
        if h1:
            result.pack_size_g = _parse_weight_g(h1.get_text())

    if result.price_gbp and result.pack_size_g:
        result.cost_per_100g = result.price_gbp / (result.pack_size_g / 100.0)

    return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "sainsburys.co.uk": _parse_sainsburys,
    "asda.com": _parse_asda,
    "tesco.com": _parse_tesco,
}


def extract_from_html(html: str, url: str) -> ProviderResult:
    """Parse HTML and extract product data using the best-matching provider."""
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(url).hostname or ""
    for domain, parser_fn in _PROVIDERS.items():
        if domain in host:
            return parser_fn(soup, url)
    return _parse_generic(soup, url)


def extract_from_url(url: str, fetch_fn=None) -> ProviderResult:
    """Fetch *url* and extract product data. *fetch_fn* may be injected for testing."""
    fetcher = fetch_fn or _default_fetch
    html = fetcher(url)
    return extract_from_html(html, url)
