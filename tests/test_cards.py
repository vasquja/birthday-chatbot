from src.chat.cards import (
    build_vote_card,
    build_voting_closed_card,
    build_tally_card,
    build_restaurant_card,
)


PLAN_ID = "users-123-2026"
OPTIONS = ["2026-04-25", "2026-05-02", "2026-05-09"]
MEMBERS = ["users/123", "users/456", "users/789"]
VOTES = {"users/123": ["2026-05-02"]}
MEMBER_NAMES = {"users/123": "Jason", "users/456": "Mike", "users/789": "Chris"}
DEADLINE = "Tue Apr 27, 9 PM ET"


def test_vote_card_structure():
    card = build_vote_card(PLAN_ID, "Jason", OPTIONS, MEMBERS, VOTES, MEMBER_NAMES, DEADLINE)
    assert "cardsV2" in card
    card_body = card["cardsV2"][0]["card"]
    assert "Jason" in card_body["header"]["title"]
    # Has widgets
    assert len(card_body["sections"]) > 0


def test_vote_card_has_date_buttons():
    card = build_vote_card(PLAN_ID, "Jason", OPTIONS, MEMBERS, VOTES, MEMBER_NAMES, DEADLINE)
    text = str(card)
    assert "Apr 25" in text
    assert "May 2" in text
    assert "May 9" in text


def test_vote_card_none_option():
    card = build_vote_card(PLAN_ID, "Jason", OPTIONS, MEMBERS, VOTES, MEMBER_NAMES, DEADLINE)
    assert "None" in str(card)


def test_vote_card_tally_section():
    card = build_vote_card(PLAN_ID, "Jason", OPTIONS, MEMBERS, VOTES, MEMBER_NAMES, DEADLINE)
    text = str(card)
    assert "Jason" in text   # voted
    assert "Mike" in text    # hasn't voted
    assert "Chris" in text


def test_voting_closed_card():
    card = build_voting_closed_card(PLAN_ID, OPTIONS)
    assert "cardsV2" in card
    assert "closed" in str(card).lower()


def test_tally_card_winner():
    card = build_tally_card(
        plan_id=PLAN_ID,
        winner="2026-05-02",
        tied_dates=[],
        vote_counts={"2026-05-02": ["users/123", "users/456"]},
        member_names=MEMBER_NAMES,
        person_name="Jason",
    )
    text = str(card)
    assert "May 2" in text
    assert "Yes" in text


def test_tally_card_tie():
    card = build_tally_card(
        plan_id=PLAN_ID,
        winner=None,
        tied_dates=["2026-05-02", "2026-05-09"],
        vote_counts={"2026-05-02": ["users/123"], "2026-05-09": ["users/456"]},
        member_names=MEMBER_NAMES,
        person_name="Jason",
    )
    text = str(card)
    assert "split" in text.lower() or "May 2" in text


def test_restaurant_card_with_date():
    restaurants = [
        {"name": "Peter Luger", "neighborhood": "Williamsburg", "google_rating": 4.5,
         "price_level": 4, "opentable_id": "12345"},
    ]
    card = build_restaurant_card(restaurants, date="2026-05-02")
    text = str(card)
    assert "Peter Luger" in text
    assert "2026-05-02" in text


def test_restaurant_card_without_date():
    restaurants = [
        {"name": "Corner Bistro", "neighborhood": "West Village", "google_rating": 4.3,
         "price_level": 2, "resy_slug": "corner-bistro-ny"},
    ]
    card = build_restaurant_card(restaurants, date=None)
    text = str(card)
    assert "Corner Bistro" in text
    # No date in Resy link
    assert "date=" not in text
