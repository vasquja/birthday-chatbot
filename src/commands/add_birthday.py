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
