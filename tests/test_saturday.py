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
