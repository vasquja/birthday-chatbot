# tests/test_cmd_next.py
from unittest.mock import MagicMock, patch
from src.commands.next_birthday import handle_next


def test_next_no_birthdays():
    b_store = MagicMock()
    b_store.get_all_sorted.return_value = []
    response = handle_next(b_store, MagicMock())
    assert "no birthdays" in response["text"].lower()


def test_next_standard():
    b_store = MagicMock()
    b_store.get_all_sorted.return_value = [
        {"user_id": "users/123", "display_name": "Jason", "birthday": "05-14"},
    ]
    p_store = MagicMock()
    p_store.get_for_person_year.return_value = None

    with patch("src.commands.next_birthday.days_until_birthday", return_value=54), \
         patch("src.commands.next_birthday.today_et") as mock_today:
        from datetime import date
        mock_today.return_value = date(2026, 3, 21)
        response = handle_next(b_store, p_store)

    assert "Jason" in response["text"]
    assert "54 days" in response["text"]
    assert "/plan" in response["text"]


def test_next_today_is_birthday():
    b_store = MagicMock()
    b_store.get_all_sorted.return_value = [
        {"user_id": "users/123", "display_name": "Jason", "birthday": "05-14"},
    ]
    p_store = MagicMock()
    p_store.get_for_person_year.return_value = None

    with patch("src.commands.next_birthday.days_until_birthday", return_value=0):
        response = handle_next(b_store, p_store)

    assert "today" in response["text"].lower()


def test_next_with_confirmed_plan():
    b_store = MagicMock()
    b_store.get_all_sorted.return_value = [
        {"user_id": "users/123", "display_name": "Jason", "birthday": "05-14"},
    ]
    p_store = MagicMock()
    p_store.get_for_person_year.return_value = {
        "status": "confirmed", "confirmed_date": "2026-05-03"
    }

    with patch("src.commands.next_birthday.days_until_birthday", return_value=54), \
         patch("src.commands.next_birthday.today_et") as mock_today:
        from datetime import date
        mock_today.return_value = date(2026, 3, 21)
        response = handle_next(b_store, p_store)

    assert "confirmed" in response["text"].lower() or "May 3" in response["text"]
