# tests/test_cmd_birthdays.py
from unittest.mock import MagicMock, patch
import pytest
from src.commands.add_birthday import handle_add_birthday
from src.commands.birthdays import handle_birthdays


def make_event(text, annotations=None):
    return {
        "message": {
            "text": text,
            "annotations": annotations or [],
        },
        "space": {"name": "spaces/AAA"},
        "user": {"name": "users/999", "displayName": "Caller"},
    }


def make_mention(user_id, display_name, start_index):
    return {
        "type": "USER_MENTION",
        "startIndex": start_index,
        "length": len(display_name) + 1,
        "userMention": {
            "user": {"name": user_id, "displayName": display_name, "type": "HUMAN"},
            "type": "MENTION",
        },
    }


# /addbirthday tests

def test_add_birthday_success(mock_firestore, mock_chat_client):
    store = MagicMock()
    store.upsert.return_value = "Added"
    event = make_event(
        "/addbirthday @Jason 1990-05-14",
        [make_mention("users/123", "Jason", 13)],
    )
    response = handle_add_birthday(event, store)
    store.upsert.assert_called_once_with("users/123", "Jason", "05-14", birth_year=1990)
    assert "Added" in response["text"]
    assert "Jason" in response["text"]
    assert "May 14" in response["text"]


def test_add_birthday_no_mention():
    event = make_event("/addbirthday 1990-05-14", [])
    store = MagicMock()
    response = handle_add_birthday(event, store)
    assert "Usage" in response["text"]
    store.upsert.assert_not_called()


def test_add_birthday_invalid_date():
    event = make_event("/addbirthday @Jason notadate", [make_mention("users/123", "Jason", 13)])
    store = MagicMock()
    response = handle_add_birthday(event, store)
    assert "parse" in response["text"].lower() or "format" in response["text"].lower()


def test_add_birthday_future_year():
    event = make_event("/addbirthday @Jason 2099-05-14", [make_mention("users/123", "Jason", 13)])
    store = MagicMock()
    response = handle_add_birthday(event, store)
    assert "year" in response["text"].lower()


# /birthdays tests

def test_birthdays_empty(mock_chat_client):
    store = MagicMock()
    store.get_all_sorted.return_value = []
    response = handle_birthdays(store)
    assert "no birthdays" in response["text"].lower()


def test_birthdays_list():
    store = MagicMock()
    store.get_all_sorted.return_value = [
        {"display_name": "Jason", "birthday": "05-14"},
        {"display_name": "Mike", "birthday": "07-04"},
    ]
    with patch("src.commands.birthdays.days_until_birthday") as mock_days:
        mock_days.side_effect = lambda b: {"05-14": 54, "07-04": 105}[b]
        response = handle_birthdays(store)
    assert "Jason" in response["text"]
    assert "May 14" in response["text"]
    assert "54 days" in response["text"]
