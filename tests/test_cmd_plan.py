# tests/test_cmd_plan.py
from unittest.mock import MagicMock, patch, call
from datetime import date, datetime
import pytest
from src.commands.plan import handle_plan


def make_event(annotations=None):
    return {
        "message": {"text": "/plan @Jason", "annotations": annotations or []},
        "space": {"name": "spaces/AAA"},
        "user": {"name": "users/456", "displayName": "Mike"},
    }


def make_mention(user_id, display_name):
    return {
        "type": "USER_MENTION",
        "userMention": {
            "user": {"name": user_id, "displayName": display_name, "type": "HUMAN"},
            "type": "MENTION",
        },
    }


def test_plan_no_mention():
    response = handle_plan(make_event([]), MagicMock(), MagicMock(), MagicMock())
    assert "Usage" in response["text"]


def test_plan_no_birthday():
    b_store = MagicMock()
    b_store.get.return_value = None
    event = make_event([make_mention("users/123", "Jason")])
    response = handle_plan(event, b_store, MagicMock(), MagicMock())
    assert "don't have a birthday" in response["text"]


def test_plan_vote_active():
    b_store = MagicMock()
    b_store.get.return_value = {"birthday": "05-14", "display_name": "Jason"}
    p_store = MagicMock()
    p_store.get_for_person_year.return_value = {"status": "voting", "tally_message_name": "spaces/AAA/messages/BBB"}
    event = make_event([make_mention("users/123", "Jason")])
    response = handle_plan(event, b_store, p_store, MagicMock())
    assert "already running" in response["text"]


def test_plan_tallied():
    b_store = MagicMock()
    b_store.get.return_value = {"birthday": "05-14", "display_name": "Jason"}
    p_store = MagicMock()
    p_store.get_for_person_year.return_value = {
        "status": "tallied", "tally_message_name": "spaces/AAA/messages/BBB"
    }
    event = make_event([make_mention("users/123", "Jason")])
    response = handle_plan(event, b_store, p_store, MagicMock())
    assert "confirm" in response["text"].lower()


def test_plan_confirmed():
    b_store = MagicMock()
    b_store.get.return_value = {"birthday": "05-14", "display_name": "Jason"}
    p_store = MagicMock()
    p_store.get_for_person_year.return_value = {
        "status": "confirmed", "confirmed_date": "2026-05-09", "tally_message_name": None
    }
    event = make_event([make_mention("users/123", "Jason")])
    response = handle_plan(event, b_store, p_store, MagicMock())
    assert "confirmed" in response["text"].lower()
    assert "May 9" in response["text"]


def test_plan_creates_plan():
    b_store = MagicMock()
    b_store.get.return_value = {"birthday": "05-14", "display_name": "Jason", "user_id": "users/123"}
    p_store = MagicMock()
    p_store.get_for_person_year.return_value = None
    p_store.plan_id.return_value = "users-123-2026"

    chat = MagicMock()
    chat.get_space_members_with_names.return_value = [
        {"name": "users/123", "displayName": "Jason"},
        {"name": "users/456", "displayName": "Mike"},
    ]
    chat.post_message.return_value = {"name": "spaces/AAA/messages/CCC"}

    event = make_event([make_mention("users/123", "Jason")])

    with patch("src.commands.plan.today_et") as mock_today, \
         patch("src.commands.plan.get_candidate_saturdays") as mock_sats, \
         patch("src.commands.plan.now_et") as mock_now:
        mock_today.return_value = date(2026, 3, 21)
        mock_sats.return_value = ["2026-05-09", "2026-05-16", "2026-05-23"]
        mock_now.return_value = datetime(2026, 3, 21, 14, 0)

        response = handle_plan(event, b_store, p_store, chat)

    p_store.create.assert_called_once()
    created_plan_id, created_data = p_store.create.call_args[0]
    assert created_plan_id == "users-123-2026"
    assert created_data["status"] == "voting"
    assert created_data["votes"] == {}
    assert created_data["birthday_person_id"] == "users/123"
    assert created_data["options"] == ["2026-05-09", "2026-05-16", "2026-05-23"]
    chat.post_message.assert_called_once()
    assert "vote" in response["text"].lower()
