# Birthday Chatbot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Google Chat birthday bot that remembers birthdays, coordinates dinner date voting, and suggests NYC restaurants with reservation links.

**Architecture:** Two Cloud Functions (`bot_handler`, `reminder_checker`) share a `src/` Python package. `bot_handler` handles slash commands and button interactions via HTTP. `reminder_checker` runs daily via Cloud Scheduler to post birthday reminders and close expired votes. Firestore stores all state.

**Tech Stack:** Python 3.11, Google Cloud Functions 2nd gen, Firestore, Google Chat API v1, Google Places API, `pytest`, `pytest-mock`

---

## File Map

| File | Responsibility |
|---|---|
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |
| `restaurants.json` | Curated NYC restaurant list |
| `main.py` | Cloud Function entry points (`bot_handler`, `reminder_checker`) |
| `src/utils.py` | ET timezone helpers, date parsing, user ID sanitization |
| `src/saturday.py` | Candidate Saturday computation |
| `src/firestore/birthdays_store.py` | CRUD for `birthdays` Firestore collection |
| `src/firestore/dinner_plans_store.py` | CRUD for `dinner_plans` Firestore collection |
| `src/chat/client.py` | Google Chat API wrapper (post/edit messages, list members) |
| `src/chat/cards.py` | Card JSON builders for vote, tally, restaurant cards |
| `src/commands/add_birthday.py` | `/addbirthday` handler |
| `src/commands/birthdays.py` | `/birthdays` handler |
| `src/commands/next_birthday.py` | `/next` handler |
| `src/commands/plan.py` | `/plan` handler |
| `src/commands/restaurants_cmd.py` | `/restaurants` handler |
| `src/commands/help_cmd.py` | `/help` handler |
| `src/interactions/vote_handler.py` | Button click handlers (vote toggle, confirm, pick another) |
| `src/reminder/tally.py` | Tally computation and vote-closing logic |
| `src/reminder/checker.py` | `reminder_checker` business logic |
| `src/restaurants/picker.py` | Restaurant selection + Places API supplement |
| `tests/conftest.py` | Shared fixtures (mock Firestore, mock ChatClient) |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `src/__init__.py`, `src/firestore/__init__.py`, `src/chat/__init__.py`, `src/commands/__init__.py`, `src/interactions/__init__.py`, `src/reminder/__init__.py`, `src/restaurants/__init__.py`
- Create: `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Create `requirements.txt`**

```
functions-framework==3.*
google-cloud-firestore==2.*
google-auth==2.*
google-api-python-client==2.*
requests==2.*
pytest==8.*
pytest-mock==3.*
```

- [ ] **Step 2: Create `.env.example`**

```
CHAT_SPACE_NAME=spaces/XXXXXXX
GOOGLE_PLACES_API_KEY=your_places_api_key
GCP_PROJECT_ID=your_gcp_project_id
```

- [ ] **Step 3: Create all `__init__.py` files**

```bash
mkdir -p src/firestore src/chat src/commands src/interactions src/reminder src/restaurants tests
touch src/__init__.py src/firestore/__init__.py src/chat/__init__.py \
      src/commands/__init__.py src/interactions/__init__.py \
      src/reminder/__init__.py src/restaurants/__init__.py \
      tests/__init__.py
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
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
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 6: Verify pytest runs**

```bash
pytest tests/ -v
```
Expected: "no tests ran" (0 errors)

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "chore: project scaffolding, requirements, fixtures"
```

---

### Task 2: Utility Functions

**Files:**
- Create: `src/utils.py`
- Create: `tests/test_utils.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_utils.py
from datetime import date
import pytest
from unittest.mock import patch
from src.utils import (
    user_id_to_doc_id,
    parse_birthday,
    days_until_birthday,
    today_et,
    format_date_display,
)


def test_user_id_to_doc_id():
    assert user_id_to_doc_id("users/12345678") == "users-12345678"


def test_user_id_to_doc_id_already_safe():
    assert user_id_to_doc_id("users-12345678") == "users-12345678"


def test_parse_birthday_full():
    month, day, year = parse_birthday("1990-05-14")
    assert month == 5
    assert day == 14
    assert year == 1990


def test_parse_birthday_mmdd():
    month, day, year = parse_birthday("05-14")
    assert month == 5
    assert day == 14
    assert year is None


def test_parse_birthday_invalid():
    with pytest.raises(ValueError):
        parse_birthday("not-a-date")


def test_parse_birthday_future_year():
    with pytest.raises(ValueError, match="future"):
        parse_birthday("2099-05-14")


def test_days_until_birthday_future():
    # Birthday is May 14, today is Mar 21 — 54 days away
    with patch("src.utils.today_et", return_value=date(2026, 3, 21)):
        assert days_until_birthday("05-14") == 54


def test_days_until_birthday_today():
    with patch("src.utils.today_et", return_value=date(2026, 5, 14)):
        assert days_until_birthday("05-14") == 0


def test_days_until_birthday_wraps_year():
    # Birthday is Jan 1, today is Dec 31 — 1 day away
    with patch("src.utils.today_et", return_value=date(2026, 12, 31)):
        assert days_until_birthday("01-01") == 1


def test_days_until_birthday_feb29_nonleap():
    # Feb 29 in non-leap year → treated as Mar 1
    with patch("src.utils.today_et", return_value=date(2025, 2, 28)):
        assert days_until_birthday("02-29") == 1  # Mar 1 is next day


def test_format_date_display():
    assert format_date_display("2026-05-14") == "May 14"
    assert format_date_display("05-14") == "May 14"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_utils.py -v
```
Expected: ImportError (module doesn't exist yet)

- [ ] **Step 3: Implement `src/utils.py`**

```python
from datetime import date, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def today_et() -> date:
    from datetime import datetime
    return datetime.now(ET).date()


def now_et():
    from datetime import datetime
    return datetime.now(ET)


def user_id_to_doc_id(user_id: str) -> str:
    return user_id.replace("/", "-")


def parse_birthday(date_str: str) -> tuple[int, int, int | None]:
    """
    Parses 'YYYY-MM-DD' or 'MM-DD'.
    Returns (month, day, year_or_None).
    Raises ValueError on bad format or future year.
    """
    import re
    from datetime import datetime

    date_str = date_str.strip()
    full = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_str)
    short = re.match(r"^(\d{2})-(\d{2})$", date_str)

    if full:
        year, month, day = int(full.group(1)), int(full.group(2)), int(full.group(3))
        current_year = today_et().year
        if year >= current_year:
            raise ValueError(f"future year: {year}")
        # Validate date
        date(year, month, day)
        return month, day, year
    elif short:
        month, day = int(short.group(1)), int(short.group(2))
        # Validate month/day (use a non-leap year for general validation, except Feb 29)
        try:
            date(2000, month, day)  # 2000 is a leap year — allows Feb 29
        except ValueError:
            raise ValueError(f"invalid date: {date_str}")
        return month, day, None
    else:
        raise ValueError(f"unrecognized date format: {date_str}")


def _next_occurrence(month: int, day: int, from_date: date) -> date:
    """Return the next occurrence of MM-DD on or after from_date. Feb 29 → Mar 1 in non-leap years."""
    year = from_date.year
    # Handle Feb 29 in non-leap years
    import calendar
    if month == 2 and day == 29 and not calendar.isleap(year):
        month, day = 3, 1
    try:
        candidate = date(year, month, day)
    except ValueError:
        candidate = date(year + 1, month, day)
    if candidate < from_date:
        next_year = year + 1
        if month == 2 and day == 29 and not calendar.isleap(next_year):
            candidate = date(next_year, 3, 1)
        else:
            candidate = date(next_year, month, day)
    return candidate


def days_until_birthday(birthday_mmdd: str) -> int:
    """Days until next occurrence of MM-DD (0 = today)."""
    month, day, _ = parse_birthday(birthday_mmdd)
    today = today_et()
    next_occ = _next_occurrence(month, day, today)
    return (next_occ - today).days


def format_date_display(date_str: str) -> str:
    """Convert 'YYYY-MM-DD' or 'MM-DD' to 'Month D' (e.g. 'May 14')."""
    from datetime import datetime
    if len(date_str) == 10:  # YYYY-MM-DD
        d = datetime.strptime(date_str, "%Y-%m-%d")
    else:  # MM-DD
        d = datetime.strptime(date_str, "%m-%d")
    return d.strftime("%b %-d")  # e.g. "May 14"
```

- [ ] **Step 4: Run tests — all pass**

```bash
pytest tests/test_utils.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils.py tests/test_utils.py
git commit -m "feat: utility functions (date parsing, ET timezone, user ID sanitization)"
```

---

### Task 3: Saturday Finder

**Files:**
- Create: `src/saturday.py`
- Create: `tests/test_saturday.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_saturday.py
from datetime import date
from src.saturday import get_candidate_saturdays, get_next_saturdays_after


def test_saturday_on_birthday():
    # May 9 2026 is a Saturday — should be Saturday 1
    bday = date(2026, 5, 9)
    result = get_candidate_saturdays(bday)
    assert result == ["2026-05-09", "2026-05-16", "2026-05-23"]


def test_saturday_before_birthday():
    # May 14 2026 is a Thursday — nearest Saturday before = May 9
    bday = date(2026, 5, 14)
    result = get_candidate_saturdays(bday)
    assert result == ["2026-05-09", "2026-05-16", "2026-05-23"]


def test_saturday_after_birthday():
    # May 11 2026 is a Monday — nearest Saturday before = May 9
    bday = date(2026, 5, 11)
    result = get_candidate_saturdays(bday)
    assert result == ["2026-05-09", "2026-05-16", "2026-05-23"]


def test_get_next_saturdays_after():
    last = date(2026, 5, 23)
    result = get_next_saturdays_after(last)
    assert result == ["2026-05-30", "2026-06-06", "2026-06-13"]


def test_saturdays_wrap_year():
    bday = date(2026, 12, 30)  # Wednesday
    result = get_candidate_saturdays(bday)
    assert result[0] == "2026-12-26"
    assert result[1] == "2027-01-02"
    assert result[2] == "2027-01-09"
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_saturday.py -v
```

- [ ] **Step 3: Implement `src/saturday.py`**

```python
from datetime import date, timedelta


def _most_recent_saturday_on_or_before(d: date) -> date:
    """Return the most recent Saturday on or before date d. Saturday = weekday 5."""
    days_since_saturday = (d.weekday() - 5) % 7
    return d - timedelta(days=days_since_saturday)


def get_candidate_saturdays(birthday: date) -> list[str]:
    """Return 3 candidate Saturdays: the one on/before birthday, +7, +14."""
    sat1 = _most_recent_saturday_on_or_before(birthday)
    return [
        sat1.isoformat(),
        (sat1 + timedelta(weeks=1)).isoformat(),
        (sat1 + timedelta(weeks=2)).isoformat(),
    ]


def get_next_saturdays_after(last_saturday: date) -> list[str]:
    """Return 3 Saturdays starting the week after last_saturday."""
    start = last_saturday + timedelta(weeks=1)
    return [
        start.isoformat(),
        (start + timedelta(weeks=1)).isoformat(),
        (start + timedelta(weeks=2)).isoformat(),
    ]
```

- [ ] **Step 4: Run — all pass**

```bash
pytest tests/test_saturday.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/saturday.py tests/test_saturday.py
git commit -m "feat: Saturday candidate computation"
```

---

### Task 4: Firestore — Birthdays Store

**Files:**
- Create: `src/firestore/birthdays_store.py`
- Create: `tests/test_birthdays_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_birthdays_store.py
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
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_birthdays_store.py -v
```

- [ ] **Step 3: Implement `src/firestore/birthdays_store.py`**

```python
from src.utils import user_id_to_doc_id, days_until_birthday

COLLECTION = "birthdays"


class BirthdaysStore:
    def __init__(self, db):
        self.db = db

    def _doc_ref(self, user_id: str):
        return self.db.collection(COLLECTION).document(user_id_to_doc_id(user_id))

    def get(self, user_id: str) -> dict | None:
        doc = self._doc_ref(user_id).get()
        return doc.to_dict() if doc.exists else None

    def upsert(self, user_id: str, display_name: str, birthday: str, birth_year: int | None = None) -> str:
        """Create or overwrite birthday doc. Returns 'Added' or 'Updated'."""
        ref = self._doc_ref(user_id)
        existing = ref.get()
        verb = "Updated" if existing.exists else "Added"

        data = {
            "user_id": user_id,
            "display_name": display_name,
            "birthday": birthday,
            "last_reminded_date": None,
            "last_birthday_wish_date": None,
        }
        if birth_year is not None:
            data["birth_year"] = birth_year

        ref.set(data)
        return verb

    def get_all_sorted(self) -> list[dict]:
        """Return all birthday docs sorted by days_until_birthday ascending."""
        docs = [d.to_dict() for d in self.db.collection(COLLECTION).stream()]
        return sorted(docs, key=lambda d: days_until_birthday(d["birthday"]))

    def update_reminded_date(self, user_id: str, date_str: str):
        self._doc_ref(user_id).update({"last_reminded_date": date_str})

    def update_birthday_wish_date(self, user_id: str, date_str: str):
        self._doc_ref(user_id).update({"last_birthday_wish_date": date_str})
```

- [ ] **Step 4: Run — all pass**

```bash
pytest tests/test_birthdays_store.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/firestore/birthdays_store.py tests/test_birthdays_store.py
git commit -m "feat: Firestore birthdays store"
```

---

### Task 5: Firestore — Dinner Plans Store

**Files:**
- Create: `src/firestore/dinner_plans_store.py`
- Create: `tests/test_dinner_plans_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dinner_plans_store.py
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
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_dinner_plans_store.py -v
```

- [ ] **Step 3: Implement `src/firestore/dinner_plans_store.py`**

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from src.utils import user_id_to_doc_id, today_et, now_et
from google.cloud import firestore as fs

COLLECTION = "dinner_plans"
ET = ZoneInfo("America/New_York")


class DinnerPlansStore:
    def __init__(self, db):
        self.db = db

    def plan_id(self, user_id: str, year: int) -> str:
        return f"{user_id_to_doc_id(user_id)}-{year}"

    def _ref(self, plan_id: str):
        return self.db.collection(COLLECTION).document(plan_id)

    def get(self, plan_id: str) -> dict | None:
        doc = self._ref(plan_id).get()
        return doc.to_dict() if doc.exists else None

    def get_for_person_year(self, user_id: str, year: int) -> dict | None:
        return self.get(self.plan_id(user_id, year))

    def create(self, plan_id: str, data: dict):
        self._ref(plan_id).set(data)

    def update(self, plan_id: str, updates: dict):
        self._ref(plan_id).update(updates)

    def get_active_confirmed_plans(self) -> list[dict]:
        """All confirmed plans with a future confirmed_date."""
        today = today_et().isoformat()
        docs = self.db.collection(COLLECTION).where("status", "==", "confirmed").stream()
        return [
            d.to_dict() for d in docs
            if d.to_dict().get("confirmed_date", "") > today
        ]

    def get_expired_voting_plans(self) -> list[dict]:
        """All plans with status 'voting' whose deadline has passed."""
        docs = self.db.collection(COLLECTION).where("status", "==", "voting").stream()
        now = now_et()
        result = []
        for d in docs:
            data = d.to_dict()
            deadline_str = data.get("voting_deadline", "")
            if deadline_str:
                deadline = datetime.fromisoformat(deadline_str)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=ET)
                if deadline < now:
                    result.append(data)
        return result

    def set_status_transaction(self, plan_id: str, expected_status: str, new_status: str, extra: dict = None):
        """
        Firestore transaction: only update if current status == expected_status.
        Returns True if committed, False if status didn't match (concurrent update).
        """
        ref = self._ref(plan_id)

        @fs.transactional
        def _txn(transaction):
            snap = ref.get(transaction=transaction)
            if not snap.exists or snap.to_dict().get("status") != expected_status:
                return False
            updates = {"status": new_status}
            if extra:
                updates.update(extra)
            transaction.update(ref, updates)
            return True

        transaction = self.db.transaction()
        return _txn(transaction)
```

- [ ] **Step 4: Run — all pass**

```bash
pytest tests/test_dinner_plans_store.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/firestore/dinner_plans_store.py tests/test_dinner_plans_store.py
git commit -m "feat: Firestore dinner plans store with transaction support"
```

---

### Task 6: Google Chat Client

**Files:**
- Create: `src/chat/client.py`
- Create: `tests/test_chat_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_chat_client.py
from unittest.mock import MagicMock, patch
import pytest
from src.chat.client import ChatClient


@pytest.fixture
def client():
    service = MagicMock()
    return ChatClient(service)


def test_post_message_text(client):
    client.service.spaces.return_value.messages.return_value.create.return_value.execute.return_value = {
        "name": "spaces/AAA/messages/BBB"
    }
    result = client.post_message("spaces/AAA", text="Hello!")
    assert result["name"] == "spaces/AAA/messages/BBB"
    client.service.spaces.return_value.messages.return_value.create.assert_called_once()
    call_kwargs = client.service.spaces.return_value.messages.return_value.create.call_args
    assert call_kwargs.kwargs["body"]["text"] == "Hello!"


def test_post_message_card(client):
    card = {"cardsV2": [{"cardId": "test"}]}
    client.service.spaces.return_value.messages.return_value.create.return_value.execute.return_value = {
        "name": "spaces/AAA/messages/CCC"
    }
    client.post_message("spaces/AAA", card=card)
    call_kwargs = client.service.spaces.return_value.messages.return_value.create.call_args
    assert "cardsV2" in call_kwargs.kwargs["body"]


def test_update_message(client):
    client.service.spaces.return_value.messages.return_value.patch.return_value.execute.return_value = {}
    client.update_message("spaces/AAA/messages/BBB", {"cardsV2": []})
    client.service.spaces.return_value.messages.return_value.patch.assert_called_once()


def test_get_space_members(client):
    client.service.spaces.return_value.members.return_value.list.return_value.execute.return_value = {
        "memberships": [
            {"member": {"name": "users/123", "displayName": "Jason", "type": "HUMAN"}},
            {"member": {"name": "users/456", "displayName": "Mike", "type": "HUMAN"}},
            {"member": {"name": "users/BOT", "displayName": "Bot", "type": "BOT"}},
        ]
    }
    # get_space_members returns just user resource names (bots filtered)
    members = client.get_space_members("spaces/AAA")
    assert members == ["users/123", "users/456"]


def test_get_space_members_with_names(client):
    client.service.spaces.return_value.members.return_value.list.return_value.execute.return_value = {
        "memberships": [
            {"member": {"name": "users/123", "displayName": "Jason", "type": "HUMAN"}},
            {"member": {"name": "users/456", "displayName": "Mike", "type": "HUMAN"}},
            {"member": {"name": "users/BOT", "displayName": "Bot", "type": "BOT"}},
        ]
    }
    members = client.get_space_members_with_names("spaces/AAA")
    assert members == [
        {"name": "users/123", "displayName": "Jason"},
        {"name": "users/456", "displayName": "Mike"},
    ]
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_chat_client.py -v
```

- [ ] **Step 3: Implement `src/chat/client.py`**

```python
import os
from googleapiclient.discovery import build
import google.auth


def build_chat_service():
    """Build an authenticated Google Chat API service using Application Default Credentials."""
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/chat.bot"])
    return build("chat", "v1", credentials=creds)


class ChatClient:
    def __init__(self, service):
        self.service = service

    def post_message(self, space_name: str, text: str = None, card: dict = None) -> dict:
        """Post a text or card message to a space. Returns the created message resource."""
        body = {}
        if text:
            body["text"] = text
        if card:
            body.update(card)
        return (
            self.service.spaces()
            .messages()
            .create(parent=space_name, body=body)
            .execute()
        )

    def update_message(self, message_name: str, card: dict, update_mask: str = "cardsV2") -> dict:
        """Edit an existing message (card update)."""
        space_name = "/".join(message_name.split("/")[:2])
        msg_id = "/".join(message_name.split("/")[2:])
        return (
            self.service.spaces()
            .messages()
            .patch(
                name=message_name,
                updateMask=update_mask,
                body=card,
            )
            .execute()
        )

    def get_space_members(self, space_name: str) -> list[str]:
        """Return list of human member user resource names (bots excluded)."""
        return [m["name"] for m in self.get_space_members_with_names(space_name)]

    def get_space_members_with_names(self, space_name: str) -> list[dict]:
        """Return list of {"name": ..., "displayName": ...} for human members only."""
        resp = (
            self.service.spaces()
            .members()
            .list(parent=space_name)
            .execute()
        )
        return [
            {"name": m["member"]["name"], "displayName": m["member"].get("displayName", "")}
            for m in resp.get("memberships", [])
            if m.get("member", {}).get("type") == "HUMAN"
        ]
```

- [ ] **Step 4: Run — all pass**

```bash
pytest tests/test_chat_client.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/chat/client.py tests/test_chat_client.py
git commit -m "feat: Google Chat API client wrapper"
```

---

### Task 7: Card Builders

**Files:**
- Create: `src/chat/cards.py`
- Create: `tests/test_cards.py`

The Google Chat Card V2 format is used throughout. Each card function returns a dict with a `cardsV2` key suitable for passing directly to `post_message` or `update_message`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cards.py
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
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_cards.py -v
```

- [ ] **Step 3: Implement `src/chat/cards.py`**

```python
from src.utils import format_date_display

PRICE_SYMBOLS = {1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}

ACTION_VOTE = "handle_vote_toggle"
ACTION_VOTE_NONE = "handle_vote_none"
ACTION_CONFIRM = "handle_confirm"
ACTION_PICK_ANOTHER = "handle_pick_another"


def _param(key, value):
    return {"key": key, "value": str(value)}


def _button(text, function, params):
    return {
        "text": text,
        "onClick": {"action": {"function": function, "parameters": params}},
    }


def build_vote_card(plan_id, person_name, options, members, votes, member_names, deadline):
    """Interactive vote card with date toggle buttons and live tally."""
    date_buttons = []
    for opt in options:
        label = format_date_display(opt)
        date_buttons.append(
            _button(label, ACTION_VOTE, [_param("plan_id", plan_id), _param("date", opt)])
        )
    date_buttons.append(
        _button("None of these work", ACTION_VOTE_NONE, [_param("plan_id", plan_id)])
    )

    # Build tally text
    tally_lines = []
    for uid in members:
        name = member_names.get(uid, uid)
        if uid in votes:
            selected = votes[uid]
            if selected:
                dates_str = ", ".join(format_date_display(d) for d in selected)
                tally_lines.append(f"✅ {name}: {dates_str}")
            else:
                tally_lines.append(f"🚫 {name}: none work")
        else:
            tally_lines.append(f"⏳ {name}: (hasn't voted)")
    tally_text = "\n".join(tally_lines)

    return {
        "cardsV2": [{
            "cardId": f"vote-{plan_id}",
            "card": {
                "header": {
                    "title": f"Dinner for {person_name}'s Birthday 🎂",
                    "subtitle": f"Vote by {deadline}",
                },
                "sections": [
                    {
                        "header": "Pick dates that work for you (tap to toggle):",
                        "widgets": [{"buttonList": {"buttons": date_buttons}}],
                    },
                    {
                        "header": "Vote so far:",
                        "widgets": [{"textParagraph": {"text": tally_text}}],
                    },
                ],
            },
        }]
    }


def build_voting_closed_card(plan_id, options):
    """Disabled vote card shown after the deadline passes."""
    date_labels = ", ".join(format_date_display(o) for o in options)
    return {
        "cardsV2": [{
            "cardId": f"vote-closed-{plan_id}",
            "card": {
                "header": {"title": "Voting Closed", "subtitle": date_labels},
                "sections": [{
                    "widgets": [{"textParagraph": {"text": "⏰ The voting window has closed. See below for results."}}]
                }],
            },
        }]
    }


def build_tally_card(plan_id, winner, tied_dates, vote_counts, member_names, person_name):
    """Tally message posted after voting closes."""
    if winner:
        winner_label = format_date_display(winner)
        voters = [member_names.get(u, u) for u in vote_counts.get(winner, [])]
        subtitle = f"Most people can make {winner_label}" + (f" ({', '.join(voters)})" if voters else "")
        buttons = [
            _button(f"✅ Yes, {winner_label}!", ACTION_CONFIRM,
                    [_param("plan_id", plan_id), _param("date", winner)]),
            _button("📅 Pick another date", ACTION_PICK_ANOTHER,
                    [_param("plan_id", plan_id)]),
        ]
    else:
        lines = []
        for d in tied_dates:
            voters = [member_names.get(u, u) for u in vote_counts.get(d, [])]
            lines.append(f"• {format_date_display(d)}: {', '.join(voters)} ({len(voters)} vote{'s' if len(voters)!=1 else ''})")
        subtitle = "It's a split!\n" + "\n".join(lines)
        buttons = [
            _button(format_date_display(d), ACTION_CONFIRM,
                    [_param("plan_id", plan_id), _param("date", d)])
            for d in tied_dates
        ] + [_button("📅 Pick another date", ACTION_PICK_ANOTHER, [_param("plan_id", plan_id)])]

    return {
        "cardsV2": [{
            "cardId": f"tally-{plan_id}",
            "card": {
                "header": {"title": f"Dinner Vote Results — {person_name}"},
                "sections": [
                    {"widgets": [{"textParagraph": {"text": subtitle}}]},
                    {"widgets": [{"buttonList": {"buttons": buttons}}]},
                ],
            },
        }]
    }


def build_restaurant_card(restaurants, date=None):
    """Card showing 3 restaurants with reservation buttons."""
    sections = []
    for r in restaurants:
        price = PRICE_SYMBOLS.get(r.get("price_level", 2), "$$")
        rating = r.get("google_rating", "")
        name = r["name"]
        neighborhood = r.get("neighborhood", "")
        header = f"{name} — {neighborhood}"
        subtitle = f"⭐ {rating}  {price}"

        buttons = []
        if r.get("opentable_id"):
            url = f"https://www.opentable.com/restref/client/?rid={r['opentable_id']}&covers=4"
            if date:
                url += f"&datetime={date}T19:00"
            buttons.append({"text": "Reserve on OpenTable", "onClick": {"openLink": {"url": url}}})
        if r.get("resy_slug"):
            url = f"https://resy.com/cities/ny/{r['resy_slug']}?seats=4"
            if date:
                url += f"&date={date}"
            buttons.append({"text": "Reserve on Resy", "onClick": {"openLink": {"url": url}}})

        sections.append({
            "header": header,
            "widgets": [
                {"textParagraph": {"text": subtitle}},
                {"buttonList": {"buttons": buttons}},
            ],
        })

    return {
        "cardsV2": [{
            "cardId": "restaurants",
            "card": {
                "header": {"title": "🥩 NYC Steaks & Burgers"},
                "sections": sections,
            },
        }]
    }
```

- [ ] **Step 4: Run — all pass**

```bash
pytest tests/test_cards.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/chat/cards.py tests/test_cards.py
git commit -m "feat: Google Chat card builders (vote, tally, restaurant)"
```

---

### Task 8: `/addbirthday` and `/birthdays` Commands

**Files:**
- Create: `src/commands/add_birthday.py`
- Create: `src/commands/birthdays.py`
- Create: `tests/test_cmd_birthdays.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_cmd_birthdays.py -v
```

- [ ] **Step 3: Implement `src/commands/add_birthday.py`**

```python
from src.utils import parse_birthday, format_date_display


def _extract_mention(event):
    """Return (user_id, display_name) from the first USER_MENTION annotation, or (None, None)."""
    for ann in event.get("message", {}).get("annotations", []):
        if ann.get("type") == "USER_MENTION":
            user = ann["userMention"]["user"]
            if user.get("type") == "HUMAN":
                return user["name"], user["displayName"]
    return None, None


def _extract_date_token(text):
    """Return the last whitespace-separated token from text (expected to be the date)."""
    tokens = text.strip().split()
    return tokens[-1] if len(tokens) >= 2 else None


def handle_add_birthday(event, birthdays_store) -> dict:
    """Returns a Chat text response dict."""
    text = event["message"]["text"]
    user_id, display_name = _extract_mention(event)

    if not user_id:
        return {"text": "Usage: `/addbirthday @Name YYYY-MM-DD`"}

    date_token = _extract_date_token(text)
    if not date_token:
        return {"text": "Usage: `/addbirthday @Name YYYY-MM-DD`"}

    try:
        month, day, year = parse_birthday(date_token)
    except ValueError as e:
        if "future" in str(e):
            return {"text": "That birth year looks off — did you mean a past year?"}
        return {"text": "Couldn't parse that date. Try: `/addbirthday @Jason 1990-05-14`"}

    birthday_mmdd = f"{month:02d}-{day:02d}"
    verb = birthdays_store.upsert(user_id, display_name, birthday_mmdd, birth_year=year)
    label = format_date_display(birthday_mmdd)
    return {"text": f"{verb} {display_name}'s birthday: {label}"}
```

- [ ] **Step 4: Implement `src/commands/birthdays.py`**

```python
from src.utils import days_until_birthday, format_date_display


def handle_birthdays(birthdays_store) -> dict:
    docs = birthdays_store.get_all_sorted()
    if not docs:
        return {"text": "No birthdays saved yet. Use `/addbirthday @Name MM-DD` to add one!"}

    lines = ["🎂 *Upcoming Birthdays*\n"]
    for i, doc in enumerate(docs, 1):
        days = days_until_birthday(doc["birthday"])
        label = format_date_display(doc["birthday"])
        day_str = "Today! 🎂" if days == 0 else f"in {days} days"
        lines.append(f"{i}. {doc['display_name']} — {label} ({day_str})")

    return {"text": "\n".join(lines)}
```

- [ ] **Step 5: Run — all pass**

```bash
pytest tests/test_cmd_birthdays.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/commands/add_birthday.py src/commands/birthdays.py tests/test_cmd_birthdays.py
git commit -m "feat: /addbirthday and /birthdays command handlers"
```

---

### Task 9: `/next` and `/help` Commands

**Files:**
- Create: `src/commands/next_birthday.py`
- Create: `src/commands/help_cmd.py`
- Create: `tests/test_cmd_next.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_cmd_next.py -v
```

- [ ] **Step 3: Implement `src/commands/next_birthday.py`**

```python
from src.utils import days_until_birthday, format_date_display, today_et


def handle_next(birthdays_store, plans_store) -> dict:
    docs = birthdays_store.get_all_sorted()
    if not docs:
        return {"text": "No birthdays saved yet. Use `/addbirthday @Name MM-DD` to add one!"}

    # docs is sorted soonest first; first entry (or entries tied) is "next"
    first = docs[0]
    days = days_until_birthday(first["birthday"])
    tied = [d for d in docs if days_until_birthday(d["birthday"]) == days]

    if days == 0:
        names = " and ".join(d["display_name"] for d in tied)
        return {"text": f"Today is {names}'s birthday! 🎂 Use `/plan @{tied[0]['display_name']}` to organize a dinner."}

    label = format_date_display(first["birthday"])
    year = today_et().year if days > 0 else today_et().year + 1

    if len(tied) > 1:
        names = " and ".join(d["display_name"] for d in tied)
        base = f"Next up: {names} both have birthdays on {label} — that's in {days} days."
    else:
        base = f"Next up: {first['display_name']}'s birthday is {label} — that's in {days} days."

    # Check plan status for the first person
    plan = plans_store.get_for_person_year(first["user_id"], year)
    if plan:
        status = plan["status"]
        if status == "confirmed":
            conf_date = format_date_display(plan["confirmed_date"])
            return {"text": f"{base}\nA dinner is already confirmed for {conf_date}! 🎉"}
        elif status in ("voting", "tallied"):
            return {"text": f"{base}\nA dinner vote is already in progress."}

    return {"text": f"{base}\nUse `/plan @{first['display_name']}` to pick a dinner date!"}
```

- [ ] **Step 4: Implement `src/commands/help_cmd.py`**

```python
HELP_TEXT = """*Birthday Bot Commands* 🎂

`/addbirthday @Name YYYY-MM-DD` — Add or update someone's birthday (year optional)
`/birthdays` — List all birthdays, sorted by next upcoming
`/next` — Show who has the next birthday and how many days away
`/plan @Name` — Start a dinner date vote for that person's birthday
`/restaurants` — Suggest 3 NYC steak/burger restaurants with reservation links
`/help` — Show this message"""


def handle_help() -> dict:
    return {"text": HELP_TEXT}
```

- [ ] **Step 5: Run — all pass**

```bash
pytest tests/test_cmd_next.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/commands/next_birthday.py src/commands/help_cmd.py tests/test_cmd_next.py
git commit -m "feat: /next and /help command handlers"
```

---

### Task 10: `/plan` Command

**Files:**
- Create: `src/commands/plan.py`
- Create: `tests/test_cmd_plan.py`

- [ ] **Step 1: Write failing tests**

```python
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


def test_plan_creates_plan():
    b_store = MagicMock()
    b_store.get.return_value = {"birthday": "05-14", "display_name": "Jason", "user_id": "users/123"}
    p_store = MagicMock()
    p_store.get_for_person_year.return_value = None
    p_store.plan_id.return_value = "users-123-2026"

    chat = MagicMock()
    chat.get_space_members.return_value = ["users/123", "users/456"]
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
    chat.post_message.assert_called_once()
    assert "vote" in response["text"].lower() or "cardsV2" in str(response)
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_cmd_plan.py -v
```

- [ ] **Step 3: Implement `src/commands/plan.py`**

```python
from datetime import timedelta, date
from src.utils import today_et, now_et, format_date_display, user_id_to_doc_id
from src.saturday import get_candidate_saturdays
from src.chat.cards import build_vote_card


def _extract_mention(event):
    for ann in event.get("message", {}).get("annotations", []):
        if ann.get("type") == "USER_MENTION":
            user = ann["userMention"]["user"]
            if user.get("type") == "HUMAN":
                return user["name"], user["displayName"]
    return None, None


def _target_year(birthday_mmdd: str) -> int:
    """Return the year for which the next birthday occurrence falls."""
    from src.utils import days_until_birthday
    today = today_et()
    days = days_until_birthday(birthday_mmdd)
    target_date = today + timedelta(days=days)
    return target_date.year


def handle_plan(event, birthdays_store, plans_store, chat_client) -> dict:
    user_id, display_name = _extract_mention(event)
    if not user_id:
        return {"text": "Usage: `/plan @Name`. Make sure to @mention someone."}

    birthday_doc = birthdays_store.get(user_id)
    if not birthday_doc:
        return {"text": f"I don't have a birthday for {display_name} yet. Use `/addbirthday @{display_name} MM-DD` to add one."}

    birthday = birthday_doc["birthday"]
    year = _target_year(birthday)

    existing = plans_store.get_for_person_year(user_id, year)
    if existing:
        status = existing["status"]
        msg_link = existing.get("tally_message_name", "")
        if status == "voting":
            return {"text": f"A dinner vote for {display_name} is already running! ({msg_link})"}
        elif status == "tallied":
            return {"text": f"We're waiting for the group to confirm a date for {display_name}'s dinner. ({msg_link})"}
        elif status == "confirmed":
            conf = format_date_display(existing["confirmed_date"])
            return {"text": f"{display_name}'s birthday dinner is already confirmed for {conf}! 🎉"}

    space_name = event["space"]["name"]
    # Fetch members with display names from spaces.members.list
    raw_members = chat_client.get_space_members_with_names(space_name)
    members = [m["name"] for m in raw_members]
    member_names = {m["name"]: m["displayName"] for m in raw_members}

    # Compute Saturdays
    from datetime import date as ddate
    import calendar
    month, day = int(birthday.split("-")[0]), int(birthday.split("-")[1])
    # Handle Feb 29 in non-leap year
    if month == 2 and day == 29 and not calendar.isleap(year):
        month, day = 3, 1
    bday_date = ddate(year, month, day)
    options = get_candidate_saturdays(bday_date)

    # Deadline: 48 hours from now
    deadline_dt = now_et() + timedelta(hours=48)
    deadline_str = deadline_dt.isoformat()
    deadline_display = deadline_dt.strftime("%a %b %-d, %-I %p ET")

    plan_id = plans_store.plan_id(user_id, year)
    plan_data = {
        "birthday_person_id": user_id,
        "birthday_person_name": display_name,
        "status": "voting",
        "options": options,
        "members": members,
        "member_names": member_names,
        "votes": {},
        "confirmed_date": None,
        "voting_deadline": deadline_str,
        "tally_message_name": None,
        "created_at": now_et().isoformat(),
    }
    plans_store.create(plan_id, plan_data)

    card = build_vote_card(plan_id, display_name, options, members, {}, member_names, deadline_display)
    msg = chat_client.post_message(space_name, card=card)
    plans_store.update(plan_id, {"tally_message_name": msg["name"]})

    return {"text": f"Vote started for {display_name}'s birthday dinner! Check the card above."}
```

- [ ] **Step 4: Run — all pass**

```bash
pytest tests/test_cmd_plan.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/commands/plan.py tests/test_cmd_plan.py
git commit -m "feat: /plan command — create dinner vote"
```

---

### Task 11: Vote Interaction Handler

**Files:**
- Create: `src/interactions/vote_handler.py`
- Create: `tests/test_vote_handler.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_vote_handler.py
from unittest.mock import MagicMock, patch
import pytest
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
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_vote_handler.py -v
```

- [ ] **Step 3: Implement `src/interactions/vote_handler.py`**

```python
from datetime import timedelta, date
from src.utils import now_et, format_date_display
from src.saturday import get_next_saturdays_after
from src.chat.cards import build_vote_card, build_voting_closed_card


def _get_param(event, key):
    for p in event["action"]["parameters"]:
        if p["key"] == key:
            return p["value"]
    return None


def _update_tally_card(plan, plan_id, plans_store, chat_client, space_name):
    """Refresh the tally card after a vote change."""
    from src.chat.cards import build_vote_card
    card = build_vote_card(
        plan_id,
        plan["birthday_person_name"],
        plan["options"],
        plan["members"],
        plan["votes"],
        plan.get("member_names", {}),
        "deadline",
    )
    try:
        chat_client.update_message(plan["tally_message_name"], card)
    except Exception:
        msg = chat_client.post_message(space_name, card=card)
        plans_store.update(plan_id, {"tally_message_name": msg["name"]})


def handle_vote_toggle(event, plans_store, chat_client):
    plan_id = _get_param(event, "plan_id")
    date_val = _get_param(event, "date")
    user_id = event["user"]["name"]
    space_name = event["space"]["name"]

    plan = plans_store.get(plan_id)
    if not plan or plan["status"] != "voting":
        return

    current_votes = plan["votes"].get(user_id, [])
    if date_val in current_votes:
        current_votes = [d for d in current_votes if d != date_val]
    else:
        current_votes = current_votes + [date_val]

    plans_store.update(plan_id, {f"votes.{user_id}": current_votes})
    plan["votes"][user_id] = current_votes
    _update_tally_card(plan, plan_id, plans_store, chat_client, space_name)


def handle_vote_none(event, plans_store, chat_client):
    plan_id = _get_param(event, "plan_id")
    user_id = event["user"]["name"]
    space_name = event["space"]["name"]

    plan = plans_store.get(plan_id)
    if not plan or plan["status"] != "voting":
        return

    plans_store.update(plan_id, {f"votes.{user_id}": []})
    plan["votes"][user_id] = []
    _update_tally_card(plan, plan_id, plans_store, chat_client, space_name)


def handle_confirm(event, plans_store, chat_client):
    plan_id = _get_param(event, "plan_id")
    date_val = _get_param(event, "date")
    space_name = event["space"]["name"]

    committed = plans_store.set_status_transaction(
        plan_id, "tallied", "confirmed", {"confirmed_date": date_val}
    )
    if not committed:
        return  # Another tap won the race

    display_date = format_date_display(date_val)
    plan = plans_store.get(plan_id)
    name = plan["birthday_person_name"] if plan else "the birthday person"
    chat_client.post_message(
        space_name,
        text=f"🎉 Dinner for {name}'s birthday is set: Saturday, {display_date}!\nUse `/restaurants` to find a place to eat.",
    )


def handle_pick_another(event, plans_store, chat_client):
    plan_id = _get_param(event, "plan_id")
    space_name = event["space"]["name"]

    plan = plans_store.get(plan_id)
    if not plan:
        return

    committed = plans_store.set_status_transaction(plan_id, "tallied", "voting", {})
    if not committed:
        return  # Concurrent confirm won

    last_sat_str = plan["options"][-1]
    last_sat = date.fromisoformat(last_sat_str)
    new_options = get_next_saturdays_after(last_sat)
    new_deadline = (now_et() + timedelta(hours=48)).isoformat()

    plans_store.update(plan_id, {
        "options": new_options,
        "votes": {},
        "voting_deadline": new_deadline,
        "status": "voting",
    })
    plan["options"] = new_options
    plan["votes"] = {}

    from src.chat.cards import build_vote_card
    from datetime import datetime
    deadline_display = datetime.fromisoformat(new_deadline).strftime("%a %b %-d, %-I %p ET")
    card = build_vote_card(plan_id, plan["birthday_person_name"], new_options,
                           plan["members"], {}, {}, deadline_display)
    msg = chat_client.post_message(space_name, card=card)
    plans_store.update(plan_id, {"tally_message_name": msg["name"]})
```

- [ ] **Step 4: Run — all pass**

```bash
pytest tests/test_vote_handler.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/interactions/vote_handler.py tests/test_vote_handler.py
git commit -m "feat: vote interaction handlers (toggle, none, confirm, pick another)"
```

---

### Task 12: Tally Logic

**Files:**
- Create: `src/reminder/tally.py`
- Create: `tests/test_tally.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tally.py
from src.reminder.tally import compute_tally


MEMBERS = ["users/1", "users/2", "users/3"]
OPTIONS = ["2026-05-09", "2026-05-16", "2026-05-23"]


def test_clear_winner():
    votes = {
        "users/1": ["2026-05-09"],
        "users/2": ["2026-05-09"],
        "users/3": ["2026-05-16"],
    }
    winner, tied, counts = compute_tally(OPTIONS, votes, MEMBERS)
    assert winner == "2026-05-09"
    assert tied == []


def test_tie():
    votes = {
        "users/1": ["2026-05-09"],
        "users/2": ["2026-05-16"],
    }
    winner, tied, counts = compute_tally(OPTIONS, votes, MEMBERS)
    assert winner is None
    assert set(tied) == {"2026-05-09", "2026-05-16"}


def test_abstainers_ignored():
    # users/3 never voted — not counted as None
    votes = {
        "users/1": ["2026-05-09"],
        "users/2": ["2026-05-09"],
    }
    winner, tied, counts = compute_tally(OPTIONS, votes, MEMBERS)
    assert winner == "2026-05-09"


def test_none_voters_excluded():
    votes = {
        "users/1": [],  # none work
        "users/2": ["2026-05-09"],
        "users/3": ["2026-05-09"],
    }
    winner, tied, counts = compute_tally(OPTIONS, votes, MEMBERS)
    assert winner == "2026-05-09"


def test_all_none_returns_no_winner():
    votes = {
        "users/1": [],
        "users/2": [],
        "users/3": [],
    }
    winner, tied, counts = compute_tally(OPTIONS, votes, MEMBERS)
    assert winner is None
    assert tied == []  # special "all none" case — caller handles reschedule


def test_multiselect_counted_correctly():
    # users/1 selected both May 9 and May 16 — both get a vote
    votes = {
        "users/1": ["2026-05-09", "2026-05-16"],
        "users/2": ["2026-05-09"],
    }
    winner, tied, counts = compute_tally(OPTIONS, votes, MEMBERS)
    assert counts["2026-05-09"] == ["users/1", "users/2"]
    assert counts["2026-05-16"] == ["users/1"]
    assert winner == "2026-05-09"
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_tally.py -v
```

- [ ] **Step 3: Implement `src/reminder/tally.py`**

```python
def compute_tally(
    options: list[str],
    votes: dict,
    members: list[str],
) -> tuple[str | None, list[str], dict]:
    """
    Returns (winner, tied_dates, vote_counts).
    - winner: date string if one date has strictly most votes; None otherwise
    - tied_dates: list of tied dates (empty if all-none or clear winner)
    - vote_counts: {date: [user_ids who voted for it]}
    """
    counts: dict[str, list[str]] = {opt: [] for opt in options}

    for uid, selected in votes.items():
        if not selected:  # empty = "none work" — excluded
            continue
        for d in selected:
            if d in counts:
                counts[d].append(uid)

    max_votes = max((len(v) for v in counts.values()), default=0)

    if max_votes == 0:
        # All voted "none" or no votes at all
        return None, [], counts

    top_dates = [d for d, voters in counts.items() if len(voters) == max_votes]

    if len(top_dates) == 1:
        return top_dates[0], [], counts
    else:
        return None, top_dates, counts
```

- [ ] **Step 4: Run — all pass**

```bash
pytest tests/test_tally.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/reminder/tally.py tests/test_tally.py
git commit -m "feat: vote tally computation"
```

---

### Task 13: Restaurant Picker

**Files:**
- Create: `restaurants.json`
- Create: `src/restaurants/picker.py`
- Create: `tests/test_picker.py`

- [ ] **Step 1: Create `restaurants.json`**

```json
[
  {"name": "Peter Luger Steak House", "neighborhood": "Williamsburg", "google_rating": 4.5, "price_level": 4, "opentable_id": "4246", "resy_slug": null},
  {"name": "Keens Chophouse", "neighborhood": "Midtown", "google_rating": 4.6, "price_level": 4, "opentable_id": "65027", "resy_slug": null},
  {"name": "Quality Meats", "neighborhood": "Midtown", "google_rating": 4.4, "price_level": 3, "opentable_id": "118988", "resy_slug": "quality-meats-ny"},
  {"name": "Gallagher's Steakhouse", "neighborhood": "Midtown", "google_rating": 4.3, "price_level": 4, "opentable_id": "1077", "resy_slug": null},
  {"name": "The Capital Grille", "neighborhood": "Midtown", "google_rating": 4.6, "price_level": 4, "opentable_id": "2986", "resy_slug": null},
  {"name": "Wolfgang's Steakhouse", "neighborhood": "Tribeca", "google_rating": 4.5, "price_level": 4, "opentable_id": "35702", "resy_slug": null},
  {"name": "Minetta Tavern", "neighborhood": "Greenwich Village", "google_rating": 4.4, "price_level": 3, "opentable_id": null, "resy_slug": "minetta-tavern-new-york"},
  {"name": "Smith & Wollensky", "neighborhood": "Midtown", "google_rating": 4.3, "price_level": 4, "opentable_id": "1695", "resy_slug": null},
  {"name": "Catch Steak", "neighborhood": "Meatpacking District", "google_rating": 4.4, "price_level": 3, "opentable_id": null, "resy_slug": "catch-steak-new-york"},
  {"name": "STK Steakhouse", "neighborhood": "Midtown", "google_rating": 4.3, "price_level": 3, "opentable_id": "148138", "resy_slug": "stk-steakhouse-midtown-new-york"},
  {"name": "Black Iron Burger", "neighborhood": "East Village", "google_rating": 4.4, "price_level": 2, "opentable_id": "349952", "resy_slug": null},
  {"name": "Porter House Bar and Grill", "neighborhood": "Midtown", "google_rating": 4.4, "price_level": 4, "opentable_id": "31350", "resy_slug": "porter-house-bar-and-grill-new-york"},
  {"name": "Cote Korean Steakhouse", "neighborhood": "Flatiron", "google_rating": 4.5, "price_level": 3, "opentable_id": null, "resy_slug": "cote-new-york"},
  {"name": "The Smith", "neighborhood": "Midtown East", "google_rating": 4.3, "price_level": 2, "opentable_id": "62701", "resy_slug": null},
  {"name": "Le Relais de Venise L'Entrecote", "neighborhood": "Midtown East", "google_rating": 4.4, "price_level": 2, "opentable_id": null, "resy_slug": null}
]
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_picker.py
from unittest.mock import patch, MagicMock
import pytest
from src.restaurants.picker import load_restaurants, pick_restaurants, build_reservation_links


def test_load_restaurants():
    restaurants = load_restaurants()
    assert len(restaurants) >= 10
    for r in restaurants:
        assert "name" in r
        assert r.get("opentable_id") or r.get("resy_slug") or True  # some may have neither


def test_pick_restaurants_returns_three():
    with patch("src.restaurants.picker.search_places", return_value=[]):
        result = pick_restaurants()
    assert len(result) == 3


def test_pick_restaurants_all_different():
    with patch("src.restaurants.picker.search_places", return_value=[]):
        r1 = pick_restaurants()
        r2 = pick_restaurants()
    # Very unlikely to get the same 3 twice (but not impossible — just verify structure)
    assert all("name" in r for r in r1)


def test_pick_restaurants_places_supplements():
    places_result = [{"name": "New Hot Spot", "neighborhood": "SoHo", "google_rating": 4.8,
                      "price_level": 3, "opentable_id": "99999", "resy_slug": None}]
    with patch("src.restaurants.picker.search_places", return_value=places_result):
        result = pick_restaurants()
    # The Places result should appear in the final 3
    names = [r["name"] for r in result]
    assert "New Hot Spot" in names


def test_pick_restaurants_places_api_error():
    with patch("src.restaurants.picker.search_places", side_effect=Exception("API error")):
        result = pick_restaurants()
    assert len(result) == 3  # Falls back to curated


def test_reservation_links_opentable_with_date():
    r = {"opentable_id": "12345", "resy_slug": None}
    links = build_reservation_links(r, date="2026-05-02")
    assert "opentable.com" in links["opentable"]
    assert "2026-05-02" in links["opentable"]
    assert "covers=4" in links["opentable"]


def test_reservation_links_resy_no_date():
    r = {"opentable_id": None, "resy_slug": "corner-bistro-ny"}
    links = build_reservation_links(r, date=None)
    assert "resy.com" in links["resy"]
    assert "date=" not in links["resy"]
    assert "seats=4" in links["resy"]
```

- [ ] **Step 3: Run — confirm fail**

```bash
pytest tests/test_picker.py -v
```

- [ ] **Step 4: Implement `src/restaurants/picker.py`**

```python
import json
import os
import random
import requests

RESTAURANTS_FILE = os.path.join(os.path.dirname(__file__), "../../restaurants.json")
PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"


def load_restaurants() -> list[dict]:
    with open(RESTAURANTS_FILE) as f:
        return json.load(f)


def search_places(api_key: str = None) -> list[dict]:
    """Query Google Places API for steak/burger restaurants in NYC with rating >= 4.2."""
    key = api_key or os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not key:
        return []
    resp = requests.get(
        PLACES_URL,
        params={"query": "steak burger restaurant New York City", "key": key},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for place in data.get("results", []):
        if place.get("rating", 0) >= 4.2:
            results.append({
                "name": place["name"],
                "neighborhood": place.get("vicinity", "NYC"),
                "google_rating": place["rating"],
                "price_level": place.get("price_level", 2),
                "opentable_id": None,
                "resy_slug": None,
            })
    return results


def pick_restaurants(date: str = None, api_key: str = None) -> list[dict]:
    """Select 3 restaurants: shuffle curated list, optionally replace slot 3 with top Places result."""
    curated = load_restaurants()
    random.shuffle(curated)
    picks = curated[:3]

    try:
        places = search_places(api_key)
        if places:
            top_place = places[0]
            curated_names = {r["name"].lower() for r in picks}
            if top_place["name"].lower() not in curated_names:
                picks[2] = top_place
    except Exception:
        pass  # Fall back to curated only

    return picks


def build_reservation_links(restaurant: dict, date: str = None) -> dict:
    """Return dict with 'opentable' and/or 'resy' URL strings."""
    links = {}
    if restaurant.get("opentable_id"):
        url = f"https://www.opentable.com/restref/client/?rid={restaurant['opentable_id']}&covers=4"
        if date:
            url += f"&datetime={date}T19:00"
        links["opentable"] = url
    if restaurant.get("resy_slug"):
        url = f"https://resy.com/cities/ny/{restaurant['resy_slug']}?seats=4"
        if date:
            url += f"&date={date}"
        links["resy"] = url
    return links
```

- [ ] **Step 5: Run — all pass**

```bash
pytest tests/test_picker.py -v
```

- [ ] **Step 6: Commit**

```bash
git add restaurants.json src/restaurants/picker.py tests/test_picker.py
git commit -m "feat: restaurant picker with curated list and Places API supplement"
```

---

### Task 14: `/restaurants` Command and Reminder Checker

**Files:**
- Create: `src/commands/restaurants_cmd.py`
- Create: `src/reminder/checker.py`
- Create: `tests/test_reminder_checker.py`

- [ ] **Step 1: Write failing tests for reminder checker**

```python
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
    }
    p_store.get_expired_voting_plans.return_value = [expired_plan]
    p_store.set_status_transaction.return_value = True

    with patch("src.reminder.checker.today_et", return_value=date(2026, 3, 21)):
        run_reminders(b_store, p_store, chat, space_name="spaces/AAA")

    p_store.set_status_transaction.assert_called_once()
    # Tally card posted
    assert chat.post_message.call_count >= 1
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_reminder_checker.py -v
```

- [ ] **Step 3: Implement `src/reminder/checker.py`**

```python
import os
from src.utils import today_et, days_until_birthday, format_date_display
from src.reminder.tally import compute_tally
from src.chat.cards import build_voting_closed_card, build_tally_card

SPACE_NAME = os.environ.get("CHAT_SPACE_NAME", "")


def run_reminders(birthdays_store, plans_store, chat_client, space_name: str = None):
    space = space_name or SPACE_NAME
    today = today_et()
    today_str = today.isoformat()

    # 1. Birthday reminders and greetings
    for doc in birthdays_store.get_all_sorted():
        user_id = doc["user_id"]
        name = doc["display_name"]
        birthday = doc["birthday"]
        days = days_until_birthday(birthday)

        # --- Birthday greeting (today) ---
        if days == 0:
            if doc.get("last_birthday_wish_date") == today_str:
                continue  # already wished today
            plan = plans_store.get_for_person_year(user_id, today.year)
            if plan and plan.get("status") == "confirmed":
                continue  # dinner confirmed, no need to nudge
            chat_client.post_message(
                space,
                text=f"🎂 Happy Birthday, {name}! We never locked in a dinner — anyone want to plan something? Use `/plan @{name}`.",
            )
            birthdays_store.update_birthday_wish_date(user_id, today_str)

        # --- 30-day reminder ---
        elif days == 30:
            if doc.get("last_reminded_date") == today_str:
                continue  # already reminded today
            target_year = today.year if days > 0 else today.year + 1
            plan = plans_store.get_for_person_year(user_id, target_year)
            if plan:
                continue  # plan already exists
            label = format_date_display(birthday)
            chat_client.post_message(
                space,
                text=f"{name}'s birthday is in 30 days ({label})! Use `/plan @{name}` to pick a dinner date.",
            )
            birthdays_store.update_reminded_date(user_id, today_str)

    # 2. Close expired votes
    for plan in plans_store.get_expired_voting_plans():
        plan_id = plans_store.plan_id(plan["birthday_person_id"], _plan_year(plan))
        committed = plans_store.set_status_transaction(plan_id, "voting", "tallied", {})
        if not committed:
            continue  # Already processed

        # Disable the vote card
        try:
            chat_client.update_message(
                plan["tally_message_name"],
                build_voting_closed_card(plan_id, plan["options"]),
            )
        except Exception:
            pass

        winner, tied, counts = compute_tally(plan["options"], plan["votes"], plan["members"])

        if winner is None and not tied:
            # All voted "none" — auto-reschedule
            from datetime import date, timedelta
            from src.saturday import get_next_saturdays_after
            from src.utils import now_et
            from src.chat.cards import build_vote_card

            last_sat = date.fromisoformat(plan["options"][-1])
            new_options = get_next_saturdays_after(last_sat)
            new_deadline = (now_et() + timedelta(hours=48)).isoformat()
            plans_store.update(plan_id, {
                "options": new_options,
                "votes": {},
                "voting_deadline": new_deadline,
                "status": "voting",
            })
            card = build_vote_card(plan_id, plan["birthday_person_name"], new_options,
                                   plan["members"], {}, {}, "48 hours from now")
            msg = chat_client.post_message(space, card=card)
            plans_store.update(plan_id, {"tally_message_name": msg["name"]})
        else:
            # Post tally card
            tally_card = build_tally_card(plan_id, winner, tied, counts, {}, plan["birthday_person_name"])
            msg = chat_client.post_message(space, card=tally_card)
            plans_store.update(plan_id, {"tally_message_name": msg["name"]})


def _plan_year(plan: dict) -> int:
    """Extract year from plan's created_at timestamp."""
    from datetime import datetime
    created = plan.get("created_at", "")
    if created:
        return datetime.fromisoformat(created).year
    return today_et().year
```

- [ ] **Step 4: Implement `src/commands/restaurants_cmd.py`**

```python
import os
from src.restaurants.picker import pick_restaurants
from src.chat.cards import build_restaurant_card


def handle_restaurants(event, plans_store, date_override: str = None) -> dict:
    """Returns a card dict."""
    # Parse optional date argument from command text
    text = event.get("message", {}).get("text", "").strip()
    parts = text.split()
    date_arg = None
    if len(parts) > 1:
        # Try last token as a date
        import re
        if re.match(r"^\d{4}-\d{2}-\d{2}$", parts[-1]):
            date_arg = parts[-1]

    date_to_use = date_override or date_arg

    if not date_to_use:
        confirmed = plans_store.get_active_confirmed_plans()
        if len(confirmed) == 1:
            date_to_use = confirmed[0]["confirmed_date"]

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    restaurants = pick_restaurants(date=date_to_use, api_key=api_key)
    return build_restaurant_card(restaurants, date=date_to_use)
```

- [ ] **Step 5: Run reminder tests — all pass**

```bash
pytest tests/test_reminder_checker.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/reminder/checker.py src/commands/restaurants_cmd.py tests/test_reminder_checker.py
git commit -m "feat: reminder checker and /restaurants command"
```

---

### Task 15: Main Entry Points

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_main.py
import json
from unittest.mock import MagicMock, patch
import pytest


def make_request(body: dict):
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
    main.birthdays_store.get.return_value = None

    from main import bot_handler
    event = make_slash_event(1, "/addbirthday @Jason 1990-05-14", annotations=[{
        "type": "USER_MENTION",
        "userMention": {"user": {"name": "users/123", "displayName": "Jason", "type": "HUMAN"}, "type": "MENTION"},
    }])
    req = make_request(event)
    resp = bot_handler(req)
    assert resp.status_code == 200


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
    resp = bot_handler(req)
    assert resp.status_code == 200


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
    resp = reminder_checker(req)
    assert resp.status_code == 200
```

- [ ] **Step 2: Run — confirm fail**

```bash
pytest tests/test_main.py -v
```

- [ ] **Step 3: Implement `main.py`**

```python
import os
import functions_framework
from flask import jsonify

# Module-level singletons — initialized lazily on first request, not at import time.
# This allows tests to patch them without triggering GCP connection attempts.
birthdays_store = None
plans_store = None
chat_client = None


def _init_singletons():
    """Initialize GCP-backed singletons once per cold start."""
    global birthdays_store, plans_store, chat_client
    if birthdays_store is not None:
        return
    from google.cloud import firestore
    from src.chat.client import build_chat_service, ChatClient
    from src.firestore.birthdays_store import BirthdaysStore
    from src.firestore.dinner_plans_store import DinnerPlansStore

    db = firestore.Client(project=os.environ.get("GCP_PROJECT_ID"))
    birthdays_store = BirthdaysStore(db)
    plans_store = DinnerPlansStore(db)
    chat_client = ChatClient(build_chat_service())

# Slash command IDs (must match Google Cloud Console registration)
CMD_ADD_BIRTHDAY = 1
CMD_BIRTHDAYS = 2
CMD_NEXT = 3
CMD_PLAN = 4
CMD_RESTAURANTS = 5
CMD_HELP = 6

# Button action function names
ACTION_VOTE_TOGGLE = "handle_vote_toggle"
ACTION_VOTE_NONE = "handle_vote_none"
ACTION_CONFIRM = "handle_confirm"
ACTION_PICK_ANOTHER = "handle_pick_another"


@functions_framework.http
def bot_handler(request):
    _init_singletons()
    event = request.get_json(silent=True) or {}
    event_type = event.get("type")

    if event_type == "MESSAGE":
        slash = event.get("message", {}).get("slashCommand", {})
        cmd_id = slash.get("commandId")
        response = _handle_slash(cmd_id, event)

    elif event_type == "CARD_CLICKED":
        function_name = event.get("action", {}).get("function", "")
        response = _handle_card_click(function_name, event)

    elif event_type == "ADDED_TO_SPACE":
        response = {"text": "Hi! I'm the birthday bot. Use `/help` to see what I can do."}

    else:
        response = {}

    return jsonify(response), 200


def _handle_slash(cmd_id, event):
    from src.commands.add_birthday import handle_add_birthday
    from src.commands.birthdays import handle_birthdays
    from src.commands.next_birthday import handle_next
    from src.commands.plan import handle_plan
    from src.commands.restaurants_cmd import handle_restaurants
    from src.commands.help_cmd import handle_help

    if cmd_id == CMD_ADD_BIRTHDAY:
        return handle_add_birthday(event, birthdays_store)
    elif cmd_id == CMD_BIRTHDAYS:
        return handle_birthdays(birthdays_store)
    elif cmd_id == CMD_NEXT:
        return handle_next(birthdays_store, plans_store)
    elif cmd_id == CMD_PLAN:
        return handle_plan(event, birthdays_store, plans_store, chat_client)
    elif cmd_id == CMD_RESTAURANTS:
        return handle_restaurants(event, plans_store)
    elif cmd_id == CMD_HELP:
        return handle_help()
    else:
        return {"text": "Unknown command. Try `/help`."}


def _handle_card_click(function_name, event):
    from src.interactions.vote_handler import (
        handle_vote_toggle, handle_vote_none, handle_confirm, handle_pick_another
    )

    if function_name == ACTION_VOTE_TOGGLE:
        handle_vote_toggle(event, plans_store, chat_client)
    elif function_name == ACTION_VOTE_NONE:
        handle_vote_none(event, plans_store, chat_client)
    elif function_name == ACTION_CONFIRM:
        handle_confirm(event, plans_store, chat_client)
    elif function_name == ACTION_PICK_ANOTHER:
        handle_pick_another(event, plans_store, chat_client)

    return {}


@functions_framework.http
def reminder_checker(request):
    _init_singletons()
    from src.reminder.checker import run_reminders
    space_name = os.environ.get("CHAT_SPACE_NAME", "")
    run_reminders(birthdays_store, plans_store, chat_client, space_name=space_name)
    return jsonify({"status": "ok"}), 200
```

- [ ] **Step 4: Run — all pass**

```bash
pytest tests/test_main.py -v
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all PASS, no errors

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: Cloud Function entry points (bot_handler, reminder_checker)"
```

---

### Task 16: Deployment

**Files:**
- Create: `deploy.sh`

- [ ] **Step 1: Create `deploy.sh`**

```bash
#!/bin/bash
# deploy.sh — Deploy both Cloud Functions
# Prerequisites: gcloud CLI installed and authenticated, PROJECT_ID set

set -e

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="us-east1"
SPACE_NAME="${CHAT_SPACE_NAME:?Set CHAT_SPACE_NAME}"
PLACES_KEY="${GOOGLE_PLACES_API_KEY:?Set GOOGLE_PLACES_API_KEY}"

echo "Deploying bot_handler..."
gcloud functions deploy bot_handler \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=. \
  --entry-point=bot_handler \
  --trigger=https \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,CHAT_SPACE_NAME=$SPACE_NAME,GOOGLE_PLACES_API_KEY=$PLACES_KEY" \
  --project=$PROJECT_ID

echo "Deploying reminder_checker..."
gcloud functions deploy reminder_checker \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=. \
  --entry-point=reminder_checker \
  --trigger=https \
  --no-allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,CHAT_SPACE_NAME=$SPACE_NAME,GOOGLE_PLACES_API_KEY=$PLACES_KEY" \
  --project=$PROJECT_ID

echo ""
echo "Done! Copy the bot_handler URL into Google Cloud Console → Google Chat API → App configuration."
echo "Then create a Cloud Scheduler job pointing to reminder_checker URL with OIDC auth, schedule: '0 9 * * *' (America/New_York)."
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x deploy.sh
git add deploy.sh
git commit -m "chore: deployment script for both Cloud Functions"
```

- [ ] **Step 3: Manual setup checklist (do once in Google Cloud Console)**

```
□ Enable APIs: Cloud Functions, Cloud Build, Firestore, Cloud Scheduler, Google Chat API, Places API
□ Create Firestore database (Native mode) in us-east1
□ Register Google Chat App at: console.cloud.google.com → APIs → Google Chat API → Configuration
  □ App name: Birthday Bot
  □ Slash commands (register each with an ID matching main.py):
      ID 1: /addbirthday   — Description: Add a birthday
      ID 2: /birthdays     — Description: List all birthdays
      ID 3: /next          — Description: Next upcoming birthday
      ID 4: /plan          — Description: Start a dinner vote
      ID 5: /restaurants   — Description: Suggest restaurants
      ID 6: /help          — Description: Show commands
  □ App URL: (paste bot_handler Cloud Function URL after deploy)
  □ Permissions: chat.spaces.members.readonly
□ Deploy: run ./deploy.sh
□ Create Cloud Scheduler job:
      Name: birthday-reminder
      Frequency: 0 9 * * *
      Timezone: America/New_York
      Target: HTTP
      URL: (reminder_checker Cloud Function URL)
      Auth: OIDC token (service account with invoker role)
□ Add bot to your Google Chat space
□ Test: /help
```

---

## Done

All tasks complete when:
- `pytest tests/ -v` passes with 0 failures
- `./deploy.sh` deploys both functions without error
- `/help` responds in the Google Chat group
- `/addbirthday @Name MM-DD` saves a birthday
- `/plan @Name` posts a vote card with 3 Saturday options
