from src.utils import format_date_display

PRICE_SYMBOLS = {1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}

ACTION_VOTE = "handle_vote_toggle"
ACTION_VOTE_NONE = "handle_vote_none"
ACTION_CONFIRM = "handle_confirm"
ACTION_PICK_ANOTHER = "handle_pick_another"


def _param(key, value):
    return {"key": key, "value": str(value)}


def _button(text, function, params):
    return {
        "text": text,
        "onClick": {"action": {"function": function, "parameters": params}},
    }


def build_vote_card(plan_id, person_name, options, members, votes, member_names, deadline):
    """Interactive vote card with date toggle buttons and live tally."""
    date_buttons = []
    for opt in options:
        label = format_date_display(opt)
        date_buttons.append(
            _button(label, ACTION_VOTE, [_param("plan_id", plan_id), _param("date", opt)])
        )
    date_buttons.append(
        _button("None of these work", ACTION_VOTE_NONE, [_param("plan_id", plan_id)])
    )

    # Build tally text
    tally_lines = []
    for uid in members:
        name = member_names.get(uid, uid)
        if uid in votes:
            selected = votes[uid]
            if selected:
                dates_str = ", ".join(format_date_display(d) for d in selected)
                tally_lines.append(f"✅ {name}: {dates_str}")
            else:
                tally_lines.append(f"🚫 {name}: none work")
        else:
            tally_lines.append(f"⏳ {name}: (hasn't voted)")
    tally_text = "\n".join(tally_lines)

    return {
        "cardsV2": [{
            "cardId": f"vote-{plan_id}",
            "card": {
                "header": {
                    "title": f"Dinner for {person_name}'s Birthday 🎂",
                    "subtitle": f"Vote by {deadline}",
                },
                "sections": [
                    {
                        "header": "Pick dates that work for you (tap to toggle):",
                        "widgets": [{"buttonList": {"buttons": date_buttons}}],
                    },
                    {
                        "header": "Vote so far:",
                        "widgets": [{"textParagraph": {"text": tally_text}}],
                    },
                ],
            },
        }]
    }


def build_voting_closed_card(plan_id, options):
    """Disabled vote card shown after the deadline passes."""
    disabled_buttons = []
    for opt in options:
        disabled_buttons.append({
            "text": format_date_display(opt),
            "disabled": True,
            "onClick": {"action": {"function": ACTION_VOTE, "parameters": [_param("plan_id", plan_id), _param("date", opt)]}},
        })
    disabled_buttons.append({
        "text": "None of these work",
        "disabled": True,
        "onClick": {"action": {"function": ACTION_VOTE_NONE, "parameters": [_param("plan_id", plan_id)]}},
    })
    return {
        "cardsV2": [{
            "cardId": f"vote-closed-{plan_id}",
            "card": {
                "header": {"title": "Voting Closed"},
                "sections": [
                    {
                        "widgets": [{"textParagraph": {"text": "⏰ The voting window has closed. See below for results."}}]
                    },
                    {
                        "header": "Options that were voted on:",
                        "widgets": [{"buttonList": {"buttons": disabled_buttons}}],
                    },
                ],
            },
        }]
    }


def build_tally_card(plan_id, winner, tied_dates, vote_counts, member_names, person_name):
    """Tally message posted after voting closes."""
    if winner:
        winner_label = format_date_display(winner)
        voters = [member_names.get(u, u) for u in vote_counts.get(winner, [])]
        subtitle = f"Most people can make {winner_label}" + (f" ({', '.join(voters)})" if voters else "")
        buttons = [
            _button(f"✅ Yes, {winner_label}!", ACTION_CONFIRM,
                    [_param("plan_id", plan_id), _param("date", winner)]),
            _button("📅 Pick another date", ACTION_PICK_ANOTHER,
                    [_param("plan_id", plan_id)]),
        ]
    else:
        lines = []
        for d in tied_dates:
            voters = [member_names.get(u, u) for u in vote_counts.get(d, [])]
            lines.append(f"• {format_date_display(d)}: {', '.join(voters)} ({len(voters)} vote{'s' if len(voters)!=1 else ''})")
        subtitle = "It's a split!\n" + "\n".join(lines)
        buttons = [
            _button(format_date_display(d), ACTION_CONFIRM,
                    [_param("plan_id", plan_id), _param("date", d)])
            for d in tied_dates
        ] + [_button("📅 Pick another date", ACTION_PICK_ANOTHER, [_param("plan_id", plan_id)])]

    return {
        "cardsV2": [{
            "cardId": f"tally-{plan_id}",
            "card": {
                "header": {"title": f"Dinner Vote Results — {person_name}"},
                "sections": [
                    {"widgets": [{"textParagraph": {"text": subtitle}}]},
                    {"widgets": [{"buttonList": {"buttons": buttons}}]},
                ],
            },
        }]
    }


def build_restaurant_card(restaurants, date=None):
    """Card showing up to 3 restaurants with reservation buttons."""
    sections = []
    for r in restaurants:
        price = PRICE_SYMBOLS.get(r.get("price_level", 2), "$$")
        rating = r.get("google_rating", "")
        name = r["name"]
        neighborhood = r.get("neighborhood", "")
        header = f"{name} — {neighborhood}"
        subtitle = f"⭐ {rating}  {price}"

        buttons = []
        if r.get("opentable_id"):
            url = f"https://www.opentable.com/restref/client/?rid={r['opentable_id']}&covers=4"
            if date:
                url += f"&datetime={date}T19:00"
            buttons.append({"text": "Reserve on OpenTable", "onClick": {"openLink": {"url": url}}})
        if r.get("resy_slug"):
            url = f"https://resy.com/cities/ny/{r['resy_slug']}?seats=4"
            if date:
                url += f"&date={date}"
            buttons.append({"text": "Reserve on Resy", "onClick": {"openLink": {"url": url}}})

        sections.append({
            "header": header,
            "widgets": [
                {"textParagraph": {"text": subtitle}},
                {"buttonList": {"buttons": buttons}},
            ],
        })

    return {
        "cardsV2": [{
            "cardId": "restaurants",
            "card": {
                "header": {"title": "🥩 NYC Steaks & Burgers"},
                "sections": sections,
            },
        }]
    }
