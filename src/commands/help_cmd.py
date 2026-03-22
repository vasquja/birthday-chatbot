HELP_TEXT = """*Birthday Bot Commands* 🎂

`/addbirthday @Name YYYY-MM-DD` — Add or update someone's birthday (year optional)
`/birthdays` — List all birthdays, sorted by next upcoming
`/next` — Show who has the next birthday and how many days away
`/plan @Name` — Start a dinner date vote for that person's birthday
`/restaurants` — Suggest 3 NYC steak/burger restaurants with reservation links
`/help` — Show this message"""


def handle_help() -> dict:
    return {"text": HELP_TEXT}
