from datetime import timedelta

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
    year = (today_et() + timedelta(days=days)).year

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
