from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
import re
import calendar

ET = ZoneInfo("America/New_York")


def today_et() -> date:
    """Return today's date in Eastern Time."""
    return datetime.now(ET).date()


def now_et():
    """Return current datetime in Eastern Time."""
    return datetime.now(ET)


def user_id_to_doc_id(user_id: str) -> str:
    """Convert Google Chat user_id (e.g. 'users/12345678') to Firestore doc_id (e.g. 'users-12345678')."""
    return user_id.replace("/", "-")


def parse_birthday(date_str: str) -> tuple[int, int, int | None]:
    """
    Parses 'YYYY-MM-DD' or 'MM-DD'.
    Returns (month, day, year_or_None).
    Raises ValueError on bad format or future year.
    """
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
    if len(date_str) == 10:  # YYYY-MM-DD
        d = datetime.strptime(date_str, "%Y-%m-%d")
    else:  # MM-DD
        d = datetime.strptime(date_str, "%m-%d")
    return d.strftime("%b %-d")  # e.g. "May 14"
