def compute_tally(
    options: list[str],
    votes: dict,
    members: list[str],
) -> tuple[str | None, list[str], dict]:
    """
    Returns (winner, tied_dates, vote_counts).
    - winner: date string if one date has strictly most votes; None otherwise
    - tied_dates: list of tied dates (empty if all-none or clear winner)
    - vote_counts: {date: [user_ids who voted for it]}
    """
    counts: dict[str, list[str]] = {opt: [] for opt in options}

    for uid, selected in votes.items():
        if not selected:  # empty = "none work" — excluded
            continue
        for d in selected:
            if d in counts:
                counts[d].append(uid)

    max_votes = max((len(v) for v in counts.values()), default=0)

    if max_votes == 0:
        # All voted "none" or no votes at all
        return None, [], counts

    top_dates = [d for d, voters in counts.items() if len(voters) == max_votes]

    if len(top_dates) == 1:
        return top_dates[0], [], counts
    else:
        return None, top_dates, counts
