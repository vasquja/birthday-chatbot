# Birthday Chatbot — Design Spec

**Date:** 2026-03-21
**Status:** Approved

## Overview

A Google Chat bot for a private group of childhood friends. Its purpose is to remember everyone's birthdays, proactively remind the group ~30 days in advance, coordinate a group dinner by running a collaborative date vote, and suggest NYC steak/burger restaurants with pre-filled reservation links.

---

## Architecture

### Components

Two Python Cloud Functions on Google Cloud:

1. **`bot_handler`** — HTTP-triggered Cloud Function that receives all Google Chat events (slash commands, button interactions). Reads/writes Firestore, calls Google Places API.
2. **`reminder_checker`** — HTTP-triggered Cloud Function invoked daily by Cloud Scheduler. Checks for birthdays 30 days out, posts proactive reminders, and closes expired votes.

### Infrastructure

- **Runtime:** Python, Google Cloud Functions (2nd gen)
- **Database:** Firestore (two collections: `birthdays`, `dinner_plans`)
- **Scheduler:** Cloud Scheduler triggers `reminder_checker` daily at 9:00 AM Eastern Time
- **APIs:** Google Chat API, Google Places API
- **Config/Secrets:** All credentials and IDs stored as environment variables in Cloud Functions (or Google Secret Manager for sensitive values)

### Configuration (Environment Variables)

| Variable | Description |
|---|---|
| `CHAT_SPACE_NAME` | Google Chat space resource name (e.g., `spaces/XXXXXXX`) |
| `GOOGLE_PLACES_API_KEY` | API key for Google Places API |
| `GCP_PROJECT_ID` | Google Cloud project ID for Firestore |

### Deployment Prerequisites

Before first deploy, the following must be configured in Google Cloud Console:
1. Register the bot as a **Google Chat App** with slash commands (`/addbirthday`, `/birthdays`, `/next`, `/plan`, `/restaurants`, `/help`)
2. Set the **App URL** to the `bot_handler` Cloud Function's HTTPS endpoint
3. Grant the Cloud Functions service account the **`chat.spaces.members.readonly`** scope to retrieve space membership
4. Configure Cloud Scheduler to call `reminder_checker` with **OIDC token authentication** using the same service account

---

## User Identity

Google Chat identifies users by a **user resource name** (e.g., `users/12345678`). This is the primary key for all user-related data.

When a user types `/addbirthday @Jason 1990-05-14`, the `@Jason` is a Chat mention. The bot extracts:
- **`user_id`**: Chat user resource name from the mention payload (e.g., `users/12345678`) — used as Firestore document ID
- **`display_name`**: Human-readable name from the mention payload (e.g., "Jason") — used for display

This avoids name collisions. Two people named Jason will have different `user_id`s.

**Firestore document ID sanitization:** The `/` in user resource names is replaced with `-` for use as Firestore document IDs (e.g., `users-12345678`).

---

## Bot Commands

Any group member can use any command. There is no admin restriction.

| Command | Description |
|---|---|
| `/addbirthday @Name YYYY-MM-DD` | Add or update a birthday. Year is optional (`MM-DD` also accepted). |
| `/birthdays` | List all birthdays sorted by next upcoming date |
| `/next` | Show who has the next birthday and how many days away |
| `/plan @Name` | Start a dinner date vote for that person's birthday |
| `/restaurants` | Suggest 3 NYC steak/burger restaurants with reservation links |
| `/help` | List all available commands with usage examples |

### Command: `/addbirthday`

- Accepts `@mention YYYY-MM-DD` or `@mention MM-DD`
- Reads the existing Firestore document first (best-effort, not a transaction) to determine "Added" vs. "Updated" reply
- Creates or overwrites the Firestore `birthdays` document for that `user_id`
- Reply: "Added Jason's birthday: May 14" or "Updated Jason's birthday: May 14"
- **Error cases:**

| Scenario | Response |
|---|---|
| Invalid date format | "Couldn't parse that date. Try: `/addbirthday @Jason 1990-05-14`" |
| Birth year ≥ current year | "That birth year looks off — did you mean a past year?" |
| No mention provided | "Usage: `/addbirthday @Name YYYY-MM-DD`" |
| No date provided | "Usage: `/addbirthday @Name YYYY-MM-DD`" |

### Command: `/birthdays`

Lists all entries in the `birthdays` collection, sorted by next occurrence (soonest first).

**Display format:**
```
🎂 Upcoming Birthdays

1. Jason — May 14 (in 54 days)
2. Mike — Jul 4 (in 105 days)
3. Chris — Dec 25 (in 279 days)
```
Birth year is not shown. "In N days" count is relative to today in Eastern Time. If today is a birthday, it shows "Today! 🎂".

If two people share the same next birthday (same MM-DD), both are listed at the same position.

### Command: `/next`

**Display format (standard):**
```
Next up: Jason's birthday is May 14 — that's in 54 days.
Use /plan @Jason to pick a dinner date!
```

**If a dinner plan exists for that person this year:**
```
Next up: Jason's birthday is May 14 — that's in 54 days.
A dinner is already confirmed for May 3! 🎉
```
(Or: "A dinner vote is already in progress." if status is `voting` or `tallied`.)

**If today is the birthday:**
```
Today is Jason's birthday! 🎂 Use /plan @Jason to organize a dinner.
```

**Tie (two people share the next birthday):** Lists both names: "Next up: Jason and Mike both have birthdays on May 14 — that's in 54 days."

### Command: `/plan @Name`

**Error cases (checked in order):**

| Scenario | Response |
|---|---|
| No mention or missing argument | "Usage: `/plan @Name`. Make sure to @mention someone." |
| Mentioned user not in `birthdays` | "I don't have a birthday for Jason yet. Use `/addbirthday @Jason MM-DD` to add one." |
| `dinner_plans` doc exists with `status: "voting"` | "A dinner vote for Jason is already running! [link to thread]" |
| `dinner_plans` doc exists with `status: "tallied"` | "We're waiting for the group to confirm a date for Jason's dinner. [link to tally message]" |
| `dinner_plans` doc exists with `status: "confirmed"` | "Jason's birthday dinner is already confirmed for [date]! 🎉" |

**Year determination:** The plan is created for the next occurrence of the birthday. If the birthday has not yet passed this calendar year, use the current year. If it has already passed, use next year. Document ID format: `{user_id_safe}-{year}`.

**If valid:** Creates a `dinner_plans` document and posts the vote card (see Dinner Planning Flow).

### Command: `/restaurants`

- Selects 3 restaurants from the curated list (see Restaurant Picker section)
- Checks Firestore for `dinner_plans` documents with `status: "confirmed"` and `confirmed_date` in the future:
  - **Exactly one found:** Pre-fill reservation links with that date
  - **Zero or multiple found:** Generate links without a pre-filled date
- Optionally accepts a date argument: `/restaurants 2026-05-03` — overrides the date for reservation links

### Command: `/help`

Posts a formatted list of all commands with one-line descriptions and usage examples.

---

## Dinner Planning Flow (`/plan`)

### Step 1 — Post Vote Card

**Candidate Saturday computation:**
- Saturday 1: The most recent Saturday on or before the birthday (if the birthday is a Saturday, use the birthday itself)
- Saturday 2: Saturday 1 + 7 days
- Saturday 3: Saturday 1 + 14 days

Bot retrieves the current space member list via `spaces.members.list` API and stores it in `dinner_plans.members` (list of user resource names). This is used to show who hasn't voted yet.

Bot posts an interactive card to the chat with the 3 date options as multi-select toggle buttons (tapping toggles on/off; a user can select multiple dates). The card also includes a "None of these work" option and displays the voting deadline.

Firestore `dinner_plans` document is created with `status: "voting"` and `tally_message_name` set to the resource name of the posted card message.

### Step 2 — Live Tally Updates

As each person votes, the bot **edits the existing card** in place using `tally_message_name`. The updated card shows who has voted and which dates they selected:

```
Vote so far (deadline: Tue Mar 23, 9 PM ET):
✅ Jason: May 3, May 10
✅ Mike: May 3
⏳ Chris: (hasn't voted)
```

**"Hasn't voted"** is determined by checking `dinner_plans.members` against keys in `dinner_plans.votes`.

Votes are stored in Firestore immediately as the user's array of selected dates. **Re-voting is allowed** — a user tapping new options overwrites their previous vote.

**If the card message was deleted and the edit fails:** Fall back to posting a new message to the thread and updating `tally_message_name` to the new message resource name.

### Step 3 — Tally & Confirmation (48 hours)

The `reminder_checker` detects when `voting_deadline` has passed and `status` is `"voting"`. It:
1. **Immediately** sets `status: "tallied"` in Firestore (to prevent double-processing on retry)
2. Edits the vote card to show "Voting closed" and disables the buttons
3. Tallies results and posts a new message:

**Tally logic:**
- Each date receives votes equal to the number of members who included it in their array
- Members with no entry in `votes` (never voted) are treated as abstaining — not counted as "none"
- Members who selected "None of these work" (empty array `[]`) are excluded from the tally
- If all members who voted selected "None," the auto-rescheduling flow triggers (see below)

**Clear winner (one date has strictly more votes than all others):**
```
Most people can make May 3 — shall we go with that?
[✅ Yes, May 3!] [📅 Pick another date]
```

**Tie or split:**
```
It's a split!
• May 3: Jason, Mike (2 votes)
• May 10: Chris (1 vote)
Which date should we go with?
[May 3] [May 10] [📅 Pick another date]
```

`tally_message_name` is updated to the resource name of this new tally message.

### Step 4 — Confirmation

Any group member can tap a confirmation button. The bot uses a **Firestore transaction** to set `status: "confirmed"` — the first write wins; concurrent taps are no-ops.

After confirming, bot posts:
```
🎉 Dinner for Jason's birthday is set: Saturday, May 3!
Use /restaurants to find a place to eat.
```

**The [Pick another date] button:**
- Can be tapped by any group member at any time while `status: "tallied"`
- Protected by a Firestore transaction: first tap wins; if someone taps [confirm] and [pick another] simultaneously, whichever transaction commits first wins
- Resets: replaces `options` with 3 new Saturdays (starting the week after the last proposed Saturday), clears `votes`, resets `voting_deadline` to 48 hours from now, sets `status: "voting"`, posts a new vote card
- Can be triggered unlimited times

### "None of These Work" — Auto-Reschedule

If all members who submitted a vote selected "None of these work" (all `votes` entries are empty arrays), the bot posts:
```
Looks like none of those dates work. Let me suggest some new options...
```
Then auto-triggers the "Pick another date" flow (new Saturdays, reset vote, new card).

---

## Proactive Reminders (`reminder_checker`)

Runs daily at 9:00 AM Eastern Time. For each birthday in Firestore:

### 30-Day Reminder

- **Trigger:** Birthday is exactly 30 days from today (Eastern Time)
- **Skip if:** A `dinner_plans` document exists for `{user_id_safe}-{current or next year}` (any status)
- **Skip if:** `birthdays.last_reminded_date` equals today's date (idempotency guard for retries)
- **Action:** Post reminder; set `last_reminded_date` to today
- **Message:** "Jason's birthday is in 30 days (May 14)! Use `/plan @Jason` to pick a dinner date."

### Birthday Greeting

- **Trigger:** Today is the birthday (MM-DD matches today in Eastern Time)
- **Skip if:** A `dinner_plans` document with `status: "confirmed"` exists for this year
- **Skip if:** `birthdays.last_birthday_wish_date` equals today's date (idempotency guard)
- **Action:** Post greeting; set `last_birthday_wish_date` to today
- **Message:** "🎂 Happy Birthday, Jason! We never locked in a dinner — anyone want to plan something? Use `/plan @Jason`."

### Close Expired Votes

- **Trigger:** A `dinner_plans` document has `status: "voting"` and `voting_deadline < now`
- **Action:** Set `status: "tallied"` (transaction), then post the tally message (Step 3 above)

---

## Restaurant Picker

### `restaurants.json` Schema

Stored in the repo root. Array of restaurant objects:

```json
[
  {
    "name": "Peter Luger",
    "neighborhood": "Williamsburg",
    "google_rating": 4.5,
    "price_level": 4,
    "opentable_id": "12345",
    "resy_slug": "peter-luger-ny"
  }
]
```

- `opentable_id`: optional string — the OpenTable restaurant ID (omit if not on OpenTable)
- `resy_slug`: optional string — the Resy URL slug (omit if not on Resy)
- At least one of `opentable_id` or `resy_slug` must be present
- `price_level`: integer 1–4 (displayed as $–$$$$)

### Selection Logic

1. Load all entries from `restaurants.json`
2. Randomly shuffle; take the top 3
3. Optionally call Google Places API for "steak OR burger restaurant" near New York City with rating ≥ 4.2 — if results are returned and none of the top 3 curated picks appear in Places results, replace the 3rd curated pick with the top Places result (for freshness)
4. On any Google Places API error, timeout, or empty result — skip Places entirely and use the 3 curated picks

### Output Card (per restaurant)

- Restaurant name + neighborhood (e.g., "Peter Luger — Williamsburg")
- Google rating (e.g., ⭐ 4.5)
- Price level (e.g., $$$$)
- [Reserve on OpenTable] button (if `opentable_id` present) and/or [Reserve on Resy] button (if `resy_slug` present)

### Reservation Link Format

**OpenTable:**
```
https://www.opentable.com/restref/client/?rid=<opentable_id>&covers=4&datetime=<YYYY-MM-DD>T19:00
```
If no date: omit the `datetime` parameter entirely.

**Resy:**
```
https://resy.com/cities/ny/<resy_slug>?date=<YYYY-MM-DD>&seats=4
```
If no date: omit the `date` parameter entirely.

Default party size: **4**. Default time: **7:00 PM** (19:00). No timezone offset in the URL.

---

## Data Model (Firestore)

### Collection: `birthdays`

Document ID: `{user_id_safe}` (e.g., `users-12345678`)

```json
{
  "user_id": "users/12345678",
  "display_name": "Jason",
  "birthday": "05-14",
  "birth_year": 1990,
  "last_reminded_date": "2026-03-21",
  "last_birthday_wish_date": "2025-05-14"
}
```

- `birthday`: MM-DD (always two-digit month and day)
- `birth_year`: optional integer; omitted if not provided
- `last_reminded_date`: YYYY-MM-DD in Eastern Time; updated after each 30-day reminder; used for idempotency
- `last_birthday_wish_date`: YYYY-MM-DD in Eastern Time; updated after each birthday greeting; used for idempotency

### Collection: `dinner_plans`

Document ID: `{user_id_safe}-{year}` (e.g., `users-12345678-2026`)

```json
{
  "birthday_person_id": "users/12345678",
  "birthday_person_name": "Jason",
  "status": "voting",
  "options": ["2026-04-25", "2026-05-02", "2026-05-09"],
  "members": ["users/12345678", "users/87654321", "users/11111111"],
  "votes": {
    "users/12345678": ["2026-05-02", "2026-05-09"],
    "users/87654321": ["2026-05-02"],
    "users/11111111": []
  },
  "confirmed_date": null,
  "voting_deadline": "2026-03-23T14:00:00-05:00",
  "tally_message_name": "spaces/XXXXXXX/messages/YYYYYYY",
  "created_at": "2026-03-21T14:00:00-05:00"
}
```

**`status` values:**
- `"voting"` — vote card is active, accepting votes
- `"tallied"` — deadline passed, tally message posted, awaiting confirmation
- `"confirmed"` — date locked in
- `"cancelled"` — reserved for future use; no current code path sets this value

**`members`:** List of Chat user resource names retrieved from `spaces.members.list` when the plan is created. Used to determine who hasn't voted yet.

**`votes`:** Map of Chat user resource name → array of selected date strings. Empty array `[]` means "none of these work." Users absent from this map have not yet voted.

**`confirmed_date`:** Always present in the document as `null` when not confirmed; set to a `YYYY-MM-DD` string when confirmed.

**`tally_message_name`:** Google Chat message resource name of the current active card (vote card initially; updated to tally message after deadline; updated again if "Pick another date" is triggered).

### Timezone

All timestamps use **Eastern Time (America/New_York)**, including daylight saving transitions. All date comparisons (birthday matching, `last_reminded_date`, `last_birthday_wish_date`, deadline checks) use Eastern Time.

---

## Error Handling & Edge Cases

### Birthday Commands

| Scenario | Behavior |
|---|---|
| Feb 29 birthday in non-leap year | Treat as Mar 1 |
| Duplicate `/addbirthday` | Overwrites record; replies "Updated Jason's birthday" |
| Invalid date format | "Couldn't parse that date. Try: `/addbirthday @Jason 1990-05-14`" |
| Birth year ≥ current year | "That birth year looks off — did you mean a past year?" |
| No mention or no date | "Usage: `/addbirthday @Name YYYY-MM-DD`" |
| Birthday is today (0 days away) | `/birthdays` and `/next` show "Today! 🎂" |
| Two people share the next birthday | Both listed in `/next` and `/birthdays` at the same position |

### Dinner Planning

| Scenario | Behavior |
|---|---|
| `/plan` with no birthday in Firestore | "I don't have a birthday for Jason yet. Use `/addbirthday @Jason MM-DD` to add one." |
| `/plan` while vote is active (`voting`) | "A dinner vote for Jason is already running! [link to thread]" |
| `/plan` while tallied (`tallied`) | "We're waiting for the group to confirm a date. [link to tally]" |
| `/plan` when dinner already confirmed | "Jason's birthday dinner is already confirmed for [date]! 🎉" |
| `/plan` with no argument | "Usage: `/plan @Name`. Make sure to @mention someone." |
| Vote after 48-hour deadline | Bot ignores the button interaction; vote card already shows "Voting closed" |
| Two people tap confirm simultaneously | Firestore transaction; first write wins; second is silently ignored |
| [Pick another date] vs. confirm race | Firestore transaction; first write wins |
| All voters select "None of these work" | Bot auto-triggers reschedule flow with 3 new Saturdays |
| Some voters select "None," rest pick dates | "None" votes excluded from tally; dates with real selections proceed normally |
| Abstaining users (never voted) | Ignored in tally; shown as "⏳ (hasn't voted)" on card |
| Re-voting (user changes selection) | Most recent vote overwrites previous; tally card updated |
| Tally card message was deleted | Fall back to posting new message; update `tally_message_name` |
| Birthday falls on a Saturday | Saturday 1 = birthday itself; Saturday 2 = +7 days; Saturday 3 = +14 days |

### Reminders

| Scenario | Behavior |
|---|---|
| Any dinner plan exists for this year | Skip 30-day reminder |
| Birthday is today, no confirmed plan | Post birthday greeting + nudge to plan |
| `reminder_checker` runs twice (retry) | `last_reminded_date` / `last_birthday_wish_date` guards prevent double-posting |
| Vote deadline passes between daily runs | Next daily run detects and closes the vote |

### Restaurant Picker

| Scenario | Behavior |
|---|---|
| Google Places API error or timeout | Skip Places; use 3 curated picks |
| Google Places returns no results | Skip Places; use 3 curated picks |
| No confirmed dinner date | Links generated without date/datetime parameter |
| Exactly one future confirmed plan | Use that plan's date in reservation links |
| Zero or multiple future confirmed plans | Links generated without date (unless `/restaurants <date>` is used) |

---

## Out of Scope

- Actual programmatic reservation booking (OpenTable/Resy APIs are not publicly available to consumers)
- Support for multiple chat spaces
- Web dashboard or admin UI
- Push notifications outside of Google Chat
- Tracking whether reservations were actually made
- Admin-only commands or permission tiers
