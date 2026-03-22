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
