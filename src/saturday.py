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
