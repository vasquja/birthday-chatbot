import os
import re
from src.restaurants.picker import pick_restaurants
from src.chat.cards import build_restaurant_card


def handle_restaurants(event, plans_store, date_override: str = None) -> dict:
    """Returns a card dict."""
    text = event.get("message", {}).get("text", "").strip()
    parts = text.split()
    date_arg = None
    if len(parts) > 1 and re.match(r"^\d{4}-\d{2}-\d{2}$", parts[-1]):
        date_arg = parts[-1]

    date_to_use = date_override or date_arg

    if not date_to_use:
        confirmed = plans_store.get_active_confirmed_plans()
        if len(confirmed) == 1:
            date_to_use = confirmed[0]["confirmed_date"]

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    restaurants = pick_restaurants(date=date_to_use, api_key=api_key)
    return build_restaurant_card(restaurants, date=date_to_use)
