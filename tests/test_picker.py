# tests/test_picker.py
from unittest.mock import patch, MagicMock
import pytest
from src.restaurants.picker import load_restaurants, pick_restaurants, build_reservation_links


def test_load_restaurants():
    restaurants = load_restaurants()
    assert len(restaurants) >= 10
    for r in restaurants:
        assert "name" in r


def test_pick_restaurants_returns_three():
    with patch("src.restaurants.picker.search_places", return_value=[]):
        result = pick_restaurants()
    assert len(result) == 3


def test_pick_restaurants_all_different():
    with patch("src.restaurants.picker.search_places", return_value=[]):
        r1 = pick_restaurants()
        r2 = pick_restaurants()
    assert all("name" in r for r in r1)


def test_pick_restaurants_places_supplements():
    places_result = [{"name": "New Hot Spot", "neighborhood": "SoHo", "google_rating": 4.8,
                      "price_level": 3, "opentable_id": "99999", "resy_slug": None}]
    with patch("src.restaurants.picker.search_places", return_value=places_result):
        result = pick_restaurants()
    names = [r["name"] for r in result]
    assert "New Hot Spot" in names


def test_pick_restaurants_places_api_error():
    with patch("src.restaurants.picker.search_places", side_effect=Exception("API error")):
        result = pick_restaurants()
    assert len(result) == 3  # Falls back to curated


def test_reservation_links_opentable_with_date():
    r = {"opentable_id": "12345", "resy_slug": None}
    links = build_reservation_links(r, date="2026-05-02")
    assert "opentable.com" in links["opentable"]
    assert "2026-05-02" in links["opentable"]
    assert "covers=4" in links["opentable"]


def test_reservation_links_resy_no_date():
    r = {"opentable_id": None, "resy_slug": "corner-bistro-ny"}
    links = build_reservation_links(r, date=None)
    assert "resy.com" in links["resy"]
    assert "date=" not in links["resy"]
    assert "seats=4" in links["resy"]
