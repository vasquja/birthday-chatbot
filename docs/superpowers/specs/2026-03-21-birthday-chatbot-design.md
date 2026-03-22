# Birthday Chatbot — Design Spec

**Date:** 2026-03-21
**Status:** Approved

## Overview

A Google Chat bot for a private group of childhood friends. Its purpose is to remember everyone's birthdays, proactively remind the group ~30 days in advance, coordinate a group dinner by running a date vote, and suggest NYC steak/burger restaurants with pre-filled reservation links.

---

## Architecture

### Components

Two Python Cloud Functions on Google Cloud:

1. **`bot_handler`** — HTTP-triggered Cloud Function that receives all Google Chat events (slash commands, button interactions). Reads/writes Firestore, calls Google Places API.
2. **`reminder_checker`** — HTTP-triggered Cloud Function invoked daily by Cloud Scheduler. Checks for birthdays ~30 days out and posts proactive reminders to the chat.

### Infrastructure

- **Runtime:** Python, Google Cloud Functions (2nd gen)
- **Database:** Firestore (two collections: `birthdays`, `dinner_plans`)
- **Scheduler:** Cloud Scheduler triggers `reminder_checker` daily
- **APIs:** Google Chat API, Google Places API
- **Messaging back to chat:** Google Chat webhook or Chat API (bot posts messages and interactive cards)

### Data Flow

```
Google Chat (group)
      │
      │ HTTP POST (slash command / button click)
      ▼
bot_handler (Cloud Function)
      ├── reads/writes ──► Firestore
      └── calls ──────────► Google Places API

Cloud Scheduler (daily)
      │
      ▼
reminder_checker (Cloud Function)
      ├── reads ──────────► Firestore (birthdays, dinner_plans)
      └── posts ──────────► Google Chat
```

---

## Bot Commands

| Command | Description |
|---|---|
| `/addbirthday @Name YYYY-MM-DD` | Add or update a person's birthday (year optional) |
| `/birthdays` | List all birthdays sorted by next upcoming date |
| `/next` | Show who has the next birthday and how many days away |
| `/plan @Name` | Start a dinner date vote for that person's birthday |
| `/restaurants` | Suggest 3 NYC steak/burger restaurants with reservation links |
| `/help` | List all available commands |

---

## Dinner Planning Flow (`/plan`)

1. Bot posts an interactive card with 2–3 Saturday options surrounding the birthday (the Saturday before, the Saturday of/after, and one more). Each option is a tappable button.
2. Each friend taps the date(s) that work for them. The bot posts a live tally update as votes come in (e.g., "Jason: May 3 ✓, Mike: May 3 ✓, Chris: May 10 ✓").
3. After **48 hours** (hard deadline, regardless of whether everyone has voted), the bot tallies results:
   - **Clear winner:** "Most people picked May 3 — confirm this date? [Yes] [Pick another]"
   - **Tie or split:** "It's split — May 3 (2 votes) vs May 10 (2 votes). Which do we go with? [May 3] [May 10]"
4. Any group member can tap to confirm. Bot posts the final confirmed date and a pre-filled restaurant reservation link (party of 4, 7:00 PM default).

---

## Proactive Reminders

The `reminder_checker` function runs daily and:
- If a birthday is **~30 days away** and no dinner plan exists for that person this year, posts: "Jason's birthday is in 28 days (May 14)! Use `/plan @Jason` to pick a dinner date."
- If a birthday is **today** and no dinner plan was ever confirmed, posts a happy birthday message and nudges the group to plan something.
- **Skips** the reminder if a `dinner_plans` record already exists for that person this year (active vote or confirmed date).

---

## Restaurant Picker

### Data Sources

- **Curated list:** ~15–20 pre-vetted NYC steak/burger restaurants (e.g., Peter Luger, Keens Chophouse, Corner Bistro, J.G. Melon, Quality Meats) with their OpenTable/Resy IDs pre-mapped. This is the primary source and ensures reservation links always work.
- **Google Places API:** Used to supplement the curated list or surface new spots. Filters: steak or burger restaurants in NYC, rating ≥ 4.2.

### Output Card (per restaurant)

- Name + neighborhood
- Google rating
- Price level ($$–$$$$)
- Pre-filled reservation link (OpenTable or Resy)

### Reservation Link Format

- **OpenTable:** `https://www.opentable.com/restref/client/?rid=<id>&datetime=<date>T19:00&covers=4`
- **Resy:** `https://resy.com/cities/ny/<slug>?date=<date>&seats=4`

If no confirmed dinner date exists yet, links are generated without a date pre-filled.

---

## Data Model (Firestore)

### Collection: `birthdays`

```json
{
  "id": "jason",
  "name": "Jason",
  "birthday": "05-14",
  "birth_year": 1990
}
```

- `id`: lowercase name, used as Firestore document ID
- `birthday`: MM-DD format
- `birth_year`: optional integer

### Collection: `dinner_plans`

```json
{
  "id": "jason-2026",
  "birthday_person": "jason",
  "status": "voting | confirmed",
  "options": ["2026-04-25", "2026-05-02", "2026-05-09"],
  "votes": {
    "jason": "2026-05-02",
    "mike": "2026-05-02",
    "chris": "2026-05-09"
  },
  "confirmed_date": null,
  "voting_deadline": "2026-03-23T00:00:00Z",
  "created_at": "2026-03-21T12:00:00Z"
}
```

---

## Error Handling & Edge Cases

### Birthday Commands

| Scenario | Behavior |
|---|---|
| Feb 29 birthday in non-leap year | Treat as Mar 1 |
| Duplicate `/addbirthday` | Overwrites existing record, confirms "Updated [Name]'s birthday" |
| Invalid date format | Bot replies with friendly correction prompt |

### Dinner Planning

| Scenario | Behavior |
|---|---|
| Vote after 48-hour deadline | Bot replies "Voting has closed, we're going with [date]" |
| `/plan` called while vote is active | Bot replies "A vote is already running!" with link to existing card |
| All options receive zero votes / "none work" | Bot suggests 3 new Saturdays from the following week |

### Reminders

| Scenario | Behavior |
|---|---|
| Dinner plan already exists for this year | Skip reminder entirely |
| Birthday is today, no plan confirmed | Post happy birthday + nudge to plan |
| Bot recovers from downtime mid-vote | Firestore preserves all state; vote resumes normally |

### Restaurant Picker

| Scenario | Behavior |
|---|---|
| Google Places returns no results | Falls back to curated list entirely |
| No confirmed dinner date when `/restaurants` called | Links generated without date pre-filled |

---

## Out of Scope

- Actual programmatic reservation booking (OpenTable/Resy APIs are not publicly available)
- Support for multiple chat spaces
- User authentication beyond Google Chat's built-in identity
- Web dashboard or admin UI
