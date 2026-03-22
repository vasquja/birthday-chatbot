from unittest.mock import MagicMock, patch
import pytest
from src.firestore.birthdays_store import BirthdaysStore


@pytest.fixture
def store():
    client = MagicMock()
    return BirthdaysStore(client)


def test_get_birthday_found(store):
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {"user_id": "users/123", "display_name": "Jason", "birthday": "05-14"}
    store.db.collection.return_value.document.return_value.get.return_value = doc

    result = store.get("users/123")
    assert result["display_name"] == "Jason"


def test_get_birthday_not_found(store):
    doc = MagicMock()
    doc.exists = False
    store.db.collection.return_value.document.return_value.get.return_value = doc

    result = store.get("users/123")
    assert result is None


def test_upsert_creates_doc(store):
    # get returns None (not found) → verb is "Added"
    doc = MagicMock()
    doc.exists = False
    store.db.collection.return_value.document.return_value.get.return_value = doc

    verb = store.upsert("users/123", "Jason", "05-14", birth_year=1990)
    assert verb == "Added"
    store.db.collection.return_value.document.return_value.set.assert_called_once()


def test_upsert_updates_existing(store):
    doc = MagicMock()
    doc.exists = True
    store.db.collection.return_value.document.return_value.get.return_value = doc

    verb = store.upsert("users/123", "Jason", "05-14")
    assert verb == "Updated"


def test_get_all_returns_sorted(store):
    docs = []
    for name, bday in [("Chris", "12-25"), ("Jason", "05-14"), ("Mike", "07-04")]:
        d = MagicMock()
        d.to_dict.return_value = {"display_name": name, "birthday": bday}
        docs.append(d)
    store.db.collection.return_value.stream.return_value = docs

    with patch("src.firestore.birthdays_store.days_until_birthday") as mock_days:
        mock_days.side_effect = lambda b: {"12-25": 279, "05-14": 54, "07-04": 105}[b]
        result = store.get_all_sorted()

    assert [r["display_name"] for r in result] == ["Jason", "Mike", "Chris"]


def test_update_reminded_date(store):
    store.update_reminded_date("users/123", "2026-03-21")
    store.db.collection.return_value.document.return_value.update.assert_called_once_with(
        {"last_reminded_date": "2026-03-21"}
    )
