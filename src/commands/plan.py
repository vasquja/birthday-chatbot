import calendar
from datetime import date as ddate, timedelta
from src.utils import today_et, now_et, format_date_display, days_until_birthday
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
    today = today_et()
    days = days_until_birthday(birthday_mmdd)
    return (today + timedelta(days=days)).year


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
    raw_members = chat_client.get_space_members_with_names(space_name)
    members = [m["name"] for m in raw_members]
    member_names = {m["name"]: m["displayName"] for m in raw_members}

    # Compute candidate Saturdays from the birthday date
    month, day = map(int, birthday.split("-"))
    if month == 2 and day == 29 and not calendar.isleap(year):
        month, day = 3, 1
    bday_date = ddate(year, month, day)
    options = get_candidate_saturdays(bday_date)

    # Deadline: 48 hours from now
    now = now_et()
    deadline_dt = now + timedelta(hours=48)
    deadline_str = deadline_dt.isoformat()
    # Format deadline for display — use portable format
    deadline_display = f"{deadline_dt.strftime('%a %b')} {deadline_dt.day}, {deadline_dt.strftime('%I').lstrip('0')} {deadline_dt.strftime('%p')} ET"

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
        "created_at": now.isoformat(),
    }
    plans_store.create(plan_id, plan_data)

    card = build_vote_card(plan_id, display_name, options, members, {}, member_names, deadline_display)
    msg = chat_client.post_message(space_name, card=card)
    plans_store.update(plan_id, {"tally_message_name": msg["name"]})

    return {"text": f"Vote started for {display_name}'s birthday dinner! Check the card above."}
