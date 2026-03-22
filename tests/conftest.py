import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def mock_gcp_imports(monkeypatch):
    """Prevent Google Cloud SDK from trying to connect at import time."""
    import sys
    for mod in ["google.cloud.firestore", "google.auth", "googleapiclient.discovery"]:
        if mod not in sys.modules:
            monkeypatch.setitem(sys.modules, mod, MagicMock())


@pytest.fixture
def mock_firestore():
    """Returns a mock Firestore client with chainable document/collection methods."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_chat_client():
    return MagicMock()


@pytest.fixture
def sample_birthday_doc():
    return {
        "user_id": "users/123",
        "display_name": "Jason",
        "birthday": "05-14",
        "birth_year": 1990,
        "last_reminded_date": None,
        "last_birthday_wish_date": None,
    }


@pytest.fixture
def sample_plan_doc():
    return {
        "birthday_person_id": "users/123",
        "birthday_person_name": "Jason",
        "status": "voting",
        "options": ["2026-04-25", "2026-05-02", "2026-05-09"],
        "members": ["users/123", "users/456", "users/789"],
        "votes": {},
        "confirmed_date": None,
        "voting_deadline": "2026-03-23T14:00:00-05:00",
        "tally_message_name": "spaces/AAA/messages/BBB",
        "created_at": "2026-03-21T14:00:00-05:00",
    }
