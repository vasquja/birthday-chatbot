# tests/test_reminder_checker.py
from unittest.mock import MagicMock, patch, call
from datetime import date
import pytest
from src.reminder.checker import run_reminders


def make_birthday(user_id, display_name, birthday, last_reminded=None, last_wish=None):
    return {
        "user_id": user_id,
        "display_name": display_name,
        "birthday": birthday,
        "last_reminded_date": last_reminded,
        "last_birthday_wish_date": last_wish,
    }


def test_posts_30_day_reminder():
    b_store = MagicMock()
    p_store = MagicMock()
    chat = MagicMock()

    b_store.get_all_sorted.return_value = [
        make_birthday("users/123", "Jason", "04-20")  # 30 days from Mar 21
    ]
    p_store.get_for_person_year.return_value = None
    p_store.get_expired_voting_plans.return_value = []

    with patch("src.reminder.checker.today_et", return_value=date(2026, 3, 21)):
        run_reminders(b_store, p_store, chat, space_name="spaces/AAA")

    chat.post_message.assert_called_once()
    msg = chat.post_message.call_args[1]["text"]
    assert "Jason" in msg
    assert "30 days" in msg


def test_skips_reminder_if_plan_exists():
    b_store = MagicMock()
    p_store = MagicMock()
    chat = MagicMock()

    b_store.get_all_sorted.return_value = [make_birthday("users/123", "Jason", "04-20")]
    p_store.get_for_person_year.return_value = {"status": "voting"}
    p_store.get_expired_voting_plans.return_value = []

    with patch("src.reminder.checker.today_et", return_value=date(2026, 3, 21)):
        run_reminders(b_store, p_store, chat, space_name="spaces/AAA")

    chat.post_message.assert_not_called()


def test_skips_reminder_if_already_reminded_today():
    b_store = MagicMock()
    p_store = MagicMock()
    chat = MagicMock()

    b_store.get_all_sorted.return_value = [
        make_birthday("users/123", "Jason", "04-20", last_reminded="2026-03-21")
    ]
    p_store.get_for_person_year.return_value = None
    p_store.get_expired_voting_plans.return_value = []

    with patch("src.reminder.checker.today_et", return_value=date(2026, 3, 21)):
        run_reminders(b_store, p_store, chat, space_name="spaces/AAA")

    chat.post_message.assert_not_called()


def test_posts_birthday_greeting():
    b_store = MagicMock()
    p_store = MagicMock()
    chat = MagicMock()

    b_store.get_all_sorted.return_value = [make_birthday("users/123", "Jason", "03-21")]
    p_store.get_for_person_year.return_value = None
    p_store.get_expired_voting_plans.return_value = []

    with patch("src.reminder.checker.today_et", return_value=date(2026, 3, 21)):
        run_reminders(b_store, p_store, chat, space_name="spaces/AAA")

    msg_args = [c[1].get("text", "") for c in chat.post_message.call_args_list]
    assert any("Happy Birthday" in m for m in msg_args)


def test_closes_expired_vote():
    b_store = MagicMock()
    p_store = MagicMock()
    chat = MagicMock()

    b_store.get_all_sorted.return_value = []
    expired_plan = {
        "birthday_person_id": "users/123",
        "birthday_person_name": "Jason",
        "status": "voting",
        "options": ["2026-04-25", "2026-05-02", "2026-05-09"],
        "members": ["users/123", "users/456"],
        "votes": {"users/123": ["2026-05-02"], "users/456": ["2026-05-02"]},
        "tally_message_name": "spaces/AAA/messages/BBB",
        "voting_deadline": "2026-03-20T00:00:00",
        "created_at": "2026-03-18T14:00:00",
    }
    p_store.get_expired_voting_plans.return_value = [expired_plan]
    p_store.set_status_transaction.return_value = True

    with patch("src.reminder.checker.today_et", return_value=date(2026, 3, 21)):
        run_reminders(b_store, p_store, chat, space_name="spaces/AAA")

    p_store.set_status_transaction.assert_called_once()
    # Tally card posted
    assert chat.post_message.call_count >= 1
