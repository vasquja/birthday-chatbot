import json
import os
import random
import requests

RESTAURANTS_FILE = os.path.join(os.path.dirname(__file__), "../../restaurants.json")
PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"


def load_restaurants() -> list[dict]:
    with open(RESTAURANTS_FILE) as f:
        return json.load(f)


def search_places(api_key: str = None) -> list[dict]:
    """Query Google Places API for steak/burger restaurants in NYC with rating >= 4.2."""
    key = api_key or os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not key:
        return []
    resp = requests.get(
        PLACES_URL,
        params={"query": "steak burger restaurant New York City", "key": key},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for place in data.get("results", []):
        if place.get("rating", 0) >= 4.2:
            results.append({
                "name": place["name"],
                "neighborhood": place.get("vicinity", "NYC"),
                "google_rating": place["rating"],
                "price_level": place.get("price_level", 2),
                "opentable_id": None,
                "resy_slug": None,
            })
    return results


def pick_restaurants(date: str = None, api_key: str = None) -> list[dict]:
    """Select 3 restaurants: shuffle curated list, optionally replace slot 3 with top Places result."""
    curated = load_restaurants()
    random.shuffle(curated)
    picks = curated[:3]

    try:
        places = search_places(api_key)
        if places:
            top_place = places[0]
            curated_names = {r["name"].lower() for r in picks}
            if top_place["name"].lower() not in curated_names:
                picks[2] = top_place
    except Exception:
        pass  # Fall back to curated only

    return picks


def build_reservation_links(restaurant: dict, date: str = None) -> dict:
    """Return dict with 'opentable' and/or 'resy' URL strings."""
    links = {}
    if restaurant.get("opentable_id"):
        url = f"https://www.opentable.com/restref/client/?rid={restaurant['opentable_id']}&covers=4"
        if date:
            url += f"&datetime={date}T19:00"
        links["opentable"] = url
    if restaurant.get("resy_slug"):
        url = f"https://resy.com/cities/ny/{restaurant['resy_slug']}?seats=4"
        if date:
            url += f"&date={date}"
        links["resy"] = url
    return links
