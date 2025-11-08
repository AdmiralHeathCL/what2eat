from __future__ import annotations

import os
import math
import re
from typing import Any, Dict, List, Optional, TypedDict
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env from project root (two levels up: project_root/manage.py, project_root/dinner/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
YELP_API_KEY = os.getenv("YELP_API_KEY")


class Location(TypedDict, total=False):
    latitude: float
    longitude: float
    address: str


class FindQuery(TypedDict, total=False):
    location: Location
    cuisines: List[str]
    dietary: List[str]
    budget: str          # "$"..."$$$$"
    vibe: List[str]
    distance_km: float
    min_rating: float
    open_now: bool
    keywords: List[str]
    limit: int
    avoid: List[str]


class Restaurant(TypedDict):
    id: str
    name: str
    rating: float
    review_count: int
    price: Optional[str]
    categories: List[str]
    url: str
    address: str
    distance_km: float
    phone: Optional[str]
    snippet: Optional[str]
    lat: Optional[float]
    lng: Optional[float]


def _require_yelp_key() -> str:
    if not YELP_API_KEY:
        raise RuntimeError("Cannot find YELP_API_KEY in .env")
    return YELP_API_KEY


def _km(meters: float) -> float:
    return round(meters / 1000.0, 2)


def _join_address(loc: Dict[str, Any]) -> str:
    parts = [p for p in [
        loc.get("address1"), loc.get("address2"), loc.get("address3"),
        loc.get("city"), loc.get("state"), loc.get("zip_code")
    ] if p]
    return ", ".join(parts)


def _category_names(cats: List[Dict[str, Any]]) -> List[str]:
    return [c.get("title") for c in (cats or [])]


def _score_business(b: Dict[str, Any], query: FindQuery) -> float:
    rating = float(b.get("rating", 0))
    reviews = float(b.get("review_count", 0))
    dist_km = _km(float(b.get("distance", 0)))
    max_km = float(query.get("distance_km", 3.0))

    # Distance penalty
    dist_pen = 0.0 if dist_km <= max_km else -0.5 * (dist_km - max_km)

    # Price alignment
    price = b.get("price")
    align = 0.0
    if "budget" in query and price:
        wanted = query["budget"]
        diff = abs(len(price) - len(wanted))
        align = max(0.0, 1.5 - 0.75 * diff)

    # Keyword bonus
    kws = set(k.lower() for k in query.get("keywords", []) or [])
    hay = (b.get("name", "") + " " +
           " ".join(_category_names(b.get("categories", [])))).lower()
    matches = sum(1 for k in kws if k in hay)
    kw_bonus = 0.5 * matches

    # Review count with diminishing returns
    review_term = min(2.0, math.log10(1 + reviews) / math.log10(500 + 1) * 2.0)

    return rating + review_term + dist_pen + align + kw_bonus


def _filter_avoid(businesses: List[Dict[str, Any]], avoid: List[str]) -> List[Dict[str, Any]]:
    if not avoid:
        return businesses
    avoid_l = [a.lower() for a in avoid]
    out: List[Dict[str, Any]] = []
    for b in businesses:
        hay = (b.get("name", "") + " " +
               " ".join(_category_names(b.get("categories", [])))).lower()
        if any(a in hay for a in avoid_l):
            continue
        out.append(b)
    return out


def _to_restaurant(b: Dict[str, Any]) -> Restaurant:
    coords = b.get("coordinates") or {}
    return {
        "id": b.get("id"),
        "name": b.get("name"),
        "rating": float(b.get("rating", 0)),
        "review_count": int(b.get("review_count", 0)),
        "price": b.get("price"),
        "categories": _category_names(b.get("categories", [])),
        "url": b.get("url"),
        "address": _join_address(b.get("location", {})),
        "distance_km": _km(float(b.get("distance", 0))),
        "phone": b.get("display_phone"),
        "snippet": None,  # filled later
        "lat": coords.get("latitude"),
        "lng": coords.get("longitude"),
    }


def _yelp_search(query: FindQuery) -> List[Dict[str, Any]]:
    key = _require_yelp_key()
    headers = {"Authorization": f"Bearer {key}"}
    params: Dict[str, Any] = {
        "limit": min(int(query.get("limit", 12)), 50),
        "sort_by": "best_match",
    }

    # Location: lat/lng or address
    loc = query.get("location", {}) or {}
    if "latitude" in loc and "longitude" in loc:
        params["latitude"] = loc["latitude"]
        params["longitude"] = loc["longitude"]
    elif "address" in loc and loc["address"]:
        params["location"] = loc["address"]
    else:
        raise ValueError("location required: either (latitude & longitude) or address")

    # Radius
    radius_m = int(min(query.get("distance_km", 3.0) * 1000, 40000))
    params["radius"] = max(100, radius_m)

    # Categories
    cats: List[str] = []
    for c in (query.get("cuisines", []) or []) + (query.get("dietary", []) or []):
        cats.append(c)
    if cats:
        params["categories"] = ",".join(cats)

    # Open now
    if query.get("open_now", True):
        params["open_now"] = "true"

    # Budget
    budget = query.get("budget")
    if budget and budget.count("$") in (1, 2, 3, 4):
        params["price"] = str(budget.count("$"))

    # Keywords / vibe → term
    terms: List[str] = []
    terms += query.get("keywords", []) or []
    terms += query.get("vibe", []) or []
    if terms:
        params["term"] = " ".join(terms)

    with httpx.Client(timeout=8.0) as client:
        r = client.get(
            "https://api.yelp.com/v3/businesses/search",
            headers=headers,
            params=params,
        )
        r.raise_for_status()
        data = r.json()

        # 🔹 Debug print: show the Yelp response structure in terminal
        print("\n=== YELP API RESPONSE ===")
        print("URL:", r.url)
        print("Status:", r.status_code)
        print("Returned businesses:", len(data.get("businesses", [])))
        for b in data.get("businesses", [])[:3]:  # show only first 3 for brevity
            print("-", b.get("name"), "| Rating:", b.get("rating"), "| Price:", b.get("price"))
        print("=========================\n")

        return data.get("businesses", []) or []


def _yelp_reviews(business_id: str) -> Optional[str]:
    key = _require_yelp_key()
    headers = {"Authorization": f"Bearer {key}"}
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(
                f"https://api.yelp.com/v3/businesses/{business_id}/reviews",
                headers=headers,
            )
            r.raise_for_status()
            js = r.json()
            reviews = js.get("reviews", [])
            if not reviews:
                return None
            text = reviews[0].get("text") or ""
            text = re.sub(r"\s+", " ", text).strip()
            return (text[:157] + "…") if len(text) > 160 else text
    except Exception:
        return None


def find_dinner(query: Dict[str, Any]) -> List[Restaurant]:
    """
    Main entry for Django views:
    - query: dict similar to your MCP FindQuery
    - returns a list of Restaurant dicts with lat/lng for the map
    """
    # Merge with defaults
    q: FindQuery = {}
    q.update(query or {})
    q.setdefault("distance_km", 3.0)
    q.setdefault("min_rating", 4.0)
    q.setdefault("open_now", True)
    q.setdefault("limit", 12)
    q.setdefault("avoid", [])

    businesses = _yelp_search(q)
    businesses = _filter_avoid(businesses, q.get("avoid", []) or [])

    # Filter by min_rating
    min_rating = float(q.get("min_rating", 0))
    businesses = [b for b in businesses if float(b.get("rating", 0)) >= min_rating]

    # Score & sort
    scored = sorted(
        businesses,
        key=lambda b: _score_business(b, q),
        reverse=True
    )

    top = scored[: int(q.get("limit", 12))]
    results: List[Restaurant] = [_to_restaurant(b) for b in top]

    # Fetch a short snippet for first few
    for i in range(min(5, len(results))):
        snippet = _yelp_reviews(results[i]["id"])
        results[i]["snippet"] = snippet

    return results
