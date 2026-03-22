from unittest.mock import MagicMock, patch, call
import pytest
from datetime import datetime
from src.firestore.dinner_plans_store import DinnerPlansStore


@pytest.fixture
def store():
    return DinnerPlansStore(MagicMock())


def test_plan_id():
    store = DinnerPlansStore(MagicMock())
    assert store.plan_id("users/123", 2026) == "users-123-2026"


def test_get_plan_found(store):
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {"status": "voting"}
    store.db.collection.return_value.document.return_value.get.return_value = doc

    result = store.get("users-123-2026")
    assert result["status"] == "voting"


def test_get_plan_not_found(store):
    doc = MagicMock()
    doc.exists = False
    store.db.collection.return_value.document.return_value.get.return_value = doc
    assert store.get("users-123-2026") is None


def test_create_plan(store):
    store.create("users-123-2026", {"status": "voting"})
    store.db.collection.return_value.document.return_value.set.assert_called_once_with(
        {"status": "voting"}
    )


def test_update_plan(store):
    store.update("users-123-2026", {"status": "tallied"})
    store.db.collection.return_value.document.return_value.update.assert_called_once_with(
        {"status": "tallied"}
    )


def test_get_active_confirmed_plans(store):
    doc1 = MagicMock()
    doc1.to_dict.return_value = {"status": "confirmed", "confirmed_date": "2026-05-03"}
    doc2 = MagicMock()
    doc2.to_dict.return_value = {"status": "confirmed", "confirmed_date": "2025-01-01"}
    store.db.collection.return_value.where.return_value.stream.return_value = [doc1, doc2]

    with patch("src.firestore.dinner_plans_store.today_et") as mock_today:
        from datetime import date
        mock_today.return_value = date(2026, 3, 21)
        result = store.get_active_confirmed_plans()

    # Only future confirmed plans
    assert len(result) == 1
    assert result[0]["confirmed_date"] == "2026-05-03"


def test_get_expired_voting_plans(store):
    doc = MagicMock()
    doc.to_dict.return_value = {"status": "voting", "voting_deadline": "2026-03-20T14:00:00-05:00"}
    store.db.collection.return_value.where.return_value.stream.return_value = [doc]

    with patch("src.firestore.dinner_plans_store.now_et") as mock_now:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        mock_now.return_value = datetime(2026, 3, 21, 14, 0, tzinfo=ZoneInfo("America/New_York"))
        result = store.get_expired_voting_plans()

    assert len(result) == 1
