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
