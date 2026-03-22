from datetime import timedelta, date, datetime
from src.utils import now_et, format_date_display
from src.saturday import get_next_saturdays_after
from src.chat.cards import build_vote_card, build_voting_closed_card


def _get_param(event, key):
    for p in event["action"]["parameters"]:
        if p["key"] == key:
            return p["value"]
    return None


def _format_deadline(deadline_raw):
    """Format ISO deadline string for display. Portable (no %-d or %-I)."""
    try:
        dt = datetime.fromisoformat(deadline_raw)
        return f"{dt.strftime('%a %b')} {dt.day}, {dt.strftime('%I').lstrip('0')} {dt.strftime('%p')} ET"
    except (ValueError, TypeError):
        return "48 hours"


def _update_tally_card(plan, plan_id, plans_store, chat_client, space_name):
    """Refresh the vote card after a vote change."""
    deadline_display = _format_deadline(plan.get("voting_deadline", ""))
    card = build_vote_card(
        plan_id,
        plan["birthday_person_name"],
        plan["options"],
        plan["members"],
        plan["votes"],
        plan.get("member_names", {}),
        deadline_display,
    )
    try:
        chat_client.update_message(plan["tally_message_name"], card)
    except Exception:
        msg = chat_client.post_message(space_name, card=card)
        plans_store.update(plan_id, {"tally_message_name": msg["name"]})


def handle_vote_toggle(event, plans_store, chat_client):
    plan_id = _get_param(event, "plan_id")
    date_val = _get_param(event, "date")
    user_id = event["user"]["name"]
    space_name = event["space"]["name"]

    plan = plans_store.get(plan_id)
    if not plan or plan["status"] != "voting":
        return

    current_votes = plan["votes"].get(user_id, [])
    if date_val in current_votes:
        current_votes = [d for d in current_votes if d != date_val]
    else:
        current_votes = current_votes + [date_val]

    plans_store.update(plan_id, {f"votes.{user_id}": current_votes})
    plan["votes"][user_id] = current_votes
    _update_tally_card(plan, plan_id, plans_store, chat_client, space_name)


def handle_vote_none(event, plans_store, chat_client):
    plan_id = _get_param(event, "plan_id")
    user_id = event["user"]["name"]
    space_name = event["space"]["name"]

    plan = plans_store.get(plan_id)
    if not plan or plan["status"] != "voting":
        return

    plans_store.update(plan_id, {f"votes.{user_id}": []})
    plan["votes"][user_id] = []
    _update_tally_card(plan, plan_id, plans_store, chat_client, space_name)


def handle_confirm(event, plans_store, chat_client):
    plan_id = _get_param(event, "plan_id")
    date_val = _get_param(event, "date")
    space_name = event["space"]["name"]

    committed = plans_store.set_status_transaction(
        plan_id, "tallied", "confirmed", {"confirmed_date": date_val}
    )
    if not committed:
        return  # Another tap won the race

    display_date = format_date_display(date_val)
    plan = plans_store.get(plan_id)
    name = plan["birthday_person_name"] if plan else "the birthday person"
    chat_client.post_message(
        space_name,
        text=f"🎉 Dinner for {name}'s birthday is set: Saturday, {display_date}!\nUse `/restaurants` to find a place to eat.",
    )


def handle_pick_another(event, plans_store, chat_client):
    plan_id = _get_param(event, "plan_id")
    space_name = event["space"]["name"]

    plan = plans_store.get(plan_id)
    if not plan:
        return

    committed = plans_store.set_status_transaction(plan_id, "tallied", "voting", {})
    if not committed:
        return  # Concurrent confirm won

    last_sat = date.fromisoformat(plan["options"][-1])
    new_options = get_next_saturdays_after(last_sat)
    now = now_et()
    new_deadline = (now + timedelta(hours=48)).isoformat()
    deadline_display = _format_deadline(new_deadline)

    plans_store.update(plan_id, {
        "options": new_options,
        "votes": {},
        "voting_deadline": new_deadline,
        "status": "voting",
    })

    card = build_vote_card(plan_id, plan["birthday_person_name"], new_options,
                           plan["members"], {}, plan.get("member_names", {}), deadline_display)
    msg = chat_client.post_message(space_name, card=card)
    plans_store.update(plan_id, {"tally_message_name": msg["name"]})
