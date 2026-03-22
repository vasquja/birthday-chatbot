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
