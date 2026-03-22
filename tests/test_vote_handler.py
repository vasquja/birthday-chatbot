# tests/test_vote_handler.py
from unittest.mock import MagicMock, patch
from src.interactions.vote_handler import handle_vote_toggle, handle_vote_none, handle_confirm, handle_pick_another


def make_click_event(function_name, params, user_id="users/456", user_name="Mike"):
    return {
        "type": "CARD_CLICKED",
        "action": {
            "function": function_name,
            "parameters": [{"key": k, "value": v} for k, v in params.items()],
        },
        "user": {"name": user_id, "displayName": user_name},
        "space": {"name": "spaces/AAA"},
    }


PLAN_ID = "users-123-2026"


def make_plan(votes=None, status="voting", options=None):
    return {
        "birthday_person_id": "users/123",
        "birthday_person_name": "Jason",
        "status": status,
        "options": options or ["2026-05-09", "2026-05-16", "2026-05-23"],
        "members": ["users/123", "users/456"],
        "votes": votes or {},
        "confirmed_date": None,
        "voting_deadline": "2099-01-01T00:00:00",
        "tally_message_name": "spaces/AAA/messages/BBB",
    }


def test_vote_toggle_adds_date():
    p_store = MagicMock()
    p_store.get.return_value = make_plan()
    chat = MagicMock()

    event = make_click_event("handle_vote_toggle", {"plan_id": PLAN_ID, "date": "2026-05-09"})
    handle_vote_toggle(event, p_store, chat)

    p_store.update.assert_called_once()
    update_args = p_store.update.call_args[0][1]
    assert "2026-05-09" in update_args[f"votes.users/456"]


def test_vote_toggle_removes_date_if_already_selected():
    p_store = MagicMock()
    p_store.get.return_value = make_plan(votes={"users/456": ["2026-05-09"]})
    chat = MagicMock()

    event = make_click_event("handle_vote_toggle", {"plan_id": PLAN_ID, "date": "2026-05-09"})
    handle_vote_toggle(event, p_store, chat)

    update_args = p_store.update.call_args[0][1]
    assert update_args[f"votes.users/456"] == []


def test_vote_none():
    p_store = MagicMock()
    p_store.get.return_value = make_plan()
    chat = MagicMock()

    event = make_click_event("handle_vote_none", {"plan_id": PLAN_ID})
    handle_vote_none(event, p_store, chat)

    update_args = p_store.update.call_args[0][1]
    assert update_args["votes.users/456"] == []


def test_confirm_succeeds():
    p_store = MagicMock()
    p_store.set_status_transaction.return_value = True
    p_store.get.return_value = make_plan(status="confirmed")
    chat = MagicMock()

    event = make_click_event("handle_confirm", {"plan_id": PLAN_ID, "date": "2026-05-09"})
    handle_confirm(event, p_store, chat)

    p_store.set_status_transaction.assert_called_once_with(
        PLAN_ID, "tallied", "confirmed", {"confirmed_date": "2026-05-09"}
    )
    chat.post_message.assert_called_once()


def test_confirm_concurrent_noop():
    """If transaction returns False (another tap won), do nothing."""
    p_store = MagicMock()
    p_store.set_status_transaction.return_value = False
    chat = MagicMock()

    event = make_click_event("handle_confirm", {"plan_id": PLAN_ID, "date": "2026-05-09"})
    handle_confirm(event, p_store, chat)
    chat.post_message.assert_not_called()


def test_pick_another():
    p_store = MagicMock()
    p_store.get.return_value = make_plan(status="tallied", options=["2026-05-09", "2026-05-16", "2026-05-23"])
    p_store.set_status_transaction.return_value = True
    chat = MagicMock()
    chat.post_message.return_value = {"name": "spaces/AAA/messages/NEW"}

    event = make_click_event("handle_pick_another", {"plan_id": PLAN_ID})
    with patch("src.interactions.vote_handler.get_next_saturdays_after") as mock_sats, \
         patch("src.interactions.vote_handler.now_et") as mock_now:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        mock_now.return_value = datetime(2026, 3, 21, 14, tzinfo=ZoneInfo("America/New_York"))
        mock_sats.return_value = ["2026-05-30", "2026-06-06", "2026-06-13"]
        handle_pick_another(event, p_store, chat)

    p_store.update.assert_called()
    chat.post_message.assert_called_once()
    # Verify the update was called with the new options and tally_message_name
    update_call = p_store.update.call_args_list[-1]
    update_data = update_call[0][1]
    assert update_data["options"] == ["2026-05-30", "2026-06-06", "2026-06-13"]
    assert update_data["votes"] == {}
    assert update_data["tally_message_name"] == "spaces/AAA/messages/NEW"


def test_vote_toggle_noop_when_status_not_voting():
    p_store = MagicMock()
    p_store.get.return_value = make_plan(status="tallied")
    chat = MagicMock()

    event = make_click_event("handle_vote_toggle", {"plan_id": PLAN_ID, "date": "2026-05-09"})
    handle_vote_toggle(event, p_store, chat)

    p_store.update.assert_not_called()
    chat.update_message.assert_not_called()


def test_vote_none_noop_when_plan_not_found():
    p_store = MagicMock()
    p_store.get.return_value = None
    chat = MagicMock()

    event = make_click_event("handle_vote_none", {"plan_id": PLAN_ID})
    handle_vote_none(event, p_store, chat)

    p_store.update.assert_not_called()
    chat.update_message.assert_not_called()
