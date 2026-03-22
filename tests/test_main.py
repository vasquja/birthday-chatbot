import json
from unittest.mock import MagicMock, patch
import pytest
from flask import Flask


_test_app = Flask(__name__)


def make_request(body: dict):
    """Create a test request with Flask app context."""
    req = MagicMock()
    req.get_json.return_value = body
    return req


def make_slash_event(command_id, text, annotations=None):
    return {
        "type": "MESSAGE",
        "message": {
            "slashCommand": {"commandId": command_id},
            "text": text,
            "annotations": annotations or [],
        },
        "space": {"name": "spaces/AAA"},
        "user": {"name": "users/999", "displayName": "Tester"},
    }


def make_card_click(function_name, params):
    return {
        "type": "CARD_CLICKED",
        "action": {
            "function": function_name,
            "parameters": [{"key": k, "value": v} for k, v in params.items()],
        },
        "space": {"name": "spaces/AAA"},
        "user": {"name": "users/999", "displayName": "Tester"},
    }


@patch("main._init_singletons")
def test_bot_handler_add_birthday(mock_init):
    import main
    main.birthdays_store = MagicMock()
    main.plans_store = MagicMock()
    main.chat_client = MagicMock()
    main.birthdays_store.upsert.return_value = "Added"

    from main import bot_handler
    event = make_slash_event(1, "/addbirthday @Jason 1990-05-14", annotations=[{
        "type": "USER_MENTION",
        "userMention": {"user": {"name": "users/123", "displayName": "Jason", "type": "HUMAN"}, "type": "MENTION"},
    }])
    req = make_request(event)
    with _test_app.app_context():
        resp = bot_handler(req)
    assert resp[1] == 200


@patch("main._init_singletons")
def test_bot_handler_card_click(mock_init):
    import main
    main.birthdays_store = MagicMock()
    main.plans_store = MagicMock()
    main.chat_client = MagicMock()
    main.plans_store.get.return_value = {
        "status": "voting",
        "options": ["2026-05-09"],
        "members": ["users/999"],
        "votes": {},
        "member_names": {},
        "tally_message_name": "spaces/AAA/messages/BBB",
        "birthday_person_name": "Jason",
        "voting_deadline": "2099-01-01",
    }
    from main import bot_handler
    event = make_card_click("handle_vote_toggle", {"plan_id": "users-123-2026", "date": "2026-05-09"})
    req = make_request(event)
    with _test_app.app_context():
        resp = bot_handler(req)
    assert resp[1] == 200


@patch("main._init_singletons")
def test_reminder_checker_runs(mock_init):
    import main
    main.birthdays_store = MagicMock()
    main.plans_store = MagicMock()
    main.chat_client = MagicMock()
    main.birthdays_store.get_all_sorted.return_value = []
    main.plans_store.get_expired_voting_plans.return_value = []
    from main import reminder_checker
    req = make_request({})
    with _test_app.app_context():
        resp = reminder_checker(req)
    assert resp[1] == 200
