import os
from datetime import date, timedelta
from src.utils import today_et, now_et, format_date_display, next_occurrence
from src.reminder.tally import compute_tally
from src.saturday import get_next_saturdays_after
from src.chat.cards import build_voting_closed_card, build_tally_card, build_vote_card


def run_reminders(birthdays_store, plans_store, chat_client, space_name: str = None):
    space = space_name or os.environ.get("CHAT_SPACE_NAME", "")
    today = today_et()
    today_str = today.isoformat()

    # 1. Birthday reminders and greetings
    for doc in birthdays_store.get_all_sorted():
        user_id = doc["user_id"]
        name = doc["display_name"]
        birthday = doc["birthday"]
        days = (next_occurrence(int(birthday[:2]), int(birthday[3:]), today) - today).days

        # --- Birthday greeting (today) ---
        if days == 0:
            if doc.get("last_birthday_wish_date") == today_str:
                continue  # already wished today
            plan = plans_store.get_for_person_year(user_id, today.year)
            if plan and plan.get("status") == "confirmed":
                continue  # dinner confirmed, skip nudge
            chat_client.post_message(
                space,
                text=f"🎂 Happy Birthday, {name}! We never locked in a dinner — anyone want to plan something? Use `/plan @{name}`.",
            )
            birthdays_store.update_birthday_wish_date(user_id, today_str)

        # --- 30-day reminder ---
        elif days == 30:
            if doc.get("last_reminded_date") == today_str:
                continue  # already reminded today
            # days == 30 so target is always current year or next (use timedelta to be safe)
            target_year = (today + timedelta(days=30)).year
            plan = plans_store.get_for_person_year(user_id, target_year)
            if plan:
                continue  # plan already exists
            label = format_date_display(birthday)
            chat_client.post_message(
                space,
                text=f"{name}'s birthday is in 30 days ({label})! Use `/plan @{name}` to pick a dinner date.",
            )
            birthdays_store.update_reminded_date(user_id, today_str)

    # 2. Close expired votes
    for plan in plans_store.get_expired_voting_plans():
        plan_id = plans_store.plan_id(plan["birthday_person_id"], _plan_year(plan))
        committed = plans_store.set_status_transaction(plan_id, "voting", "tallied", {})
        if not committed:
            continue  # Already processed

        # Disable the vote card
        try:
            chat_client.update_message(
                plan["tally_message_name"],
                build_voting_closed_card(plan_id, plan["options"]),
            )
        except Exception:
            pass

        # NOTE: compute_tally takes 2 args (options, votes) — members param was removed
        winner, tied, counts = compute_tally(plan["options"], plan["votes"])

        if winner is None and not tied:
            # All voted "none" — auto-reschedule
            last_sat = date.fromisoformat(plan["options"][-1])
            new_options = get_next_saturdays_after(last_sat)
            new_deadline = (now_et() + timedelta(hours=48)).isoformat()
            plans_store.update(plan_id, {
                "options": new_options,
                "votes": {},
                "voting_deadline": new_deadline,
                "status": "voting",
            })
            card = build_vote_card(plan_id, plan["birthday_person_name"], new_options,
                                   plan["members"], {}, plan.get("member_names", {}), "48 hours from now")
            msg = chat_client.post_message(space, card=card)
            plans_store.update(plan_id, {"tally_message_name": msg["name"]})
        else:
            # Post tally card
            tally_card = build_tally_card(
                plan_id, winner, tied, counts,
                plan.get("member_names", {}), plan["birthday_person_name"]
            )
            msg = chat_client.post_message(space, card=tally_card)
            plans_store.update(plan_id, {"tally_message_name": msg["name"]})


def _plan_year(plan: dict) -> int:
    """Extract year from plan's created_at timestamp."""
    from datetime import datetime
    created = plan.get("created_at", "")
    if created:
        return datetime.fromisoformat(created).year
    return today_et().year
