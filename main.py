import os
import logging
import functions_framework
from flask import jsonify

# Module-level singletons — initialized lazily on first request, not at import time.
# This allows tests to patch them without triggering GCP connection attempts.
birthdays_store = None
plans_store = None
chat_client = None


def _init_singletons():
    """Initialize GCP-backed singletons once per cold start."""
    global birthdays_store, plans_store, chat_client
    if all(x is not None for x in (birthdays_store, plans_store, chat_client)):
        return
    from google.cloud import firestore
    from src.chat.client import build_chat_service, ChatClient
    from src.firestore.birthdays_store import BirthdaysStore
    from src.firestore.dinner_plans_store import DinnerPlansStore

    db = firestore.Client(project=os.environ.get("GCP_PROJECT_ID"))
    bs = BirthdaysStore(db)
    ps = DinnerPlansStore(db)
    cc = ChatClient(build_chat_service())
    # Assign all at once after all constructors succeed
    birthdays_store = bs
    plans_store = ps
    chat_client = cc


# Slash command IDs (must match Google Cloud Console registration)
CMD_ADD_BIRTHDAY = 1
CMD_BIRTHDAYS = 2
CMD_NEXT = 3
CMD_PLAN = 4
CMD_RESTAURANTS = 5
CMD_HELP = 6

# Button action function names
ACTION_VOTE_TOGGLE = "handle_vote_toggle"
ACTION_VOTE_NONE = "handle_vote_none"
ACTION_CONFIRM = "handle_confirm"
ACTION_PICK_ANOTHER = "handle_pick_another"


@functions_framework.http
def bot_handler(request):
    _init_singletons()
    event = request.get_json(silent=True) or {}

    # Google Chat API uses a nested format: all data is under event['chat']
    chat = event.get("chat", {})

    if "appCommandPayload" in chat:
        # Slash command (new format)
        payload = chat["appCommandPayload"]
        metadata = payload.get("appCommandMetadata", {})
        cmd_id = int(metadata.get("appCommandId", 0))
        # Normalize to the shape our handlers expect
        normalized = {
            "type": "MESSAGE",
            "message": payload.get("message", {}),
            "space": payload.get("space", {}),
            "user": chat.get("user", {}),
        }
        response = _handle_slash(cmd_id, normalized)

    elif "interactiveDataPayload" in chat:
        # Card button click (new format)
        payload = chat["interactiveDataPayload"]
        action = payload.get("invokedFunction", "")
        params = {p["key"]: p["value"] for p in payload.get("parameters", [])}
        normalized = {
            "action": {"function": action, "parameters": payload.get("parameters", [])},
            "common": {"parameters": params},
            "space": chat.get("appCommandPayload", {}).get("space", {}),
            "user": chat.get("user", {}),
        }
        response = _handle_card_click(action, normalized)

    elif "addedToSpacePayload" in chat:
        response = {"text": "Hi! I'm the birthday bot. Use `/help` to see what I can do."}

    elif event.get("type") == "MESSAGE":
        # Legacy event format (used in tests)
        slash = event.get("message", {}).get("slashCommand", {})
        cmd_id = int(slash.get("commandId", 0))
        response = _handle_slash(cmd_id, event)

    elif event.get("type") == "CARD_CLICKED":
        function_name = event.get("action", {}).get("function", "")
        response = _handle_card_click(function_name, event)

    elif event.get("type") == "ADDED_TO_SPACE":
        response = {"text": "Hi! I'm the birthday bot. Use `/help` to see what I can do."}

    else:
        logging.warning("Unhandled event chat keys: %s", list(chat.keys()))
        response = {}

    return jsonify(response), 200


def _handle_slash(cmd_id, event):
    from src.commands.add_birthday import handle_add_birthday
    from src.commands.birthdays import handle_birthdays
    from src.commands.next_birthday import handle_next
    from src.commands.plan import handle_plan
    from src.commands.restaurants_cmd import handle_restaurants
    from src.commands.help_cmd import handle_help

    if cmd_id == CMD_ADD_BIRTHDAY:
        return handle_add_birthday(event, birthdays_store)
    elif cmd_id == CMD_BIRTHDAYS:
        return handle_birthdays(birthdays_store)
    elif cmd_id == CMD_NEXT:
        return handle_next(birthdays_store, plans_store)
    elif cmd_id == CMD_PLAN:
        return handle_plan(event, birthdays_store, plans_store, chat_client)
    elif cmd_id == CMD_RESTAURANTS:
        return handle_restaurants(event, plans_store)
    elif cmd_id == CMD_HELP:
        return handle_help()
    else:
        return {"text": "Unknown command. Try `/help`."}


def _handle_card_click(function_name, event):
    from src.interactions.vote_handler import (
        handle_vote_toggle, handle_vote_none, handle_confirm, handle_pick_another
    )
    try:
        if function_name == ACTION_VOTE_TOGGLE:
            handle_vote_toggle(event, plans_store, chat_client)
        elif function_name == ACTION_VOTE_NONE:
            handle_vote_none(event, plans_store, chat_client)
        elif function_name == ACTION_CONFIRM:
            handle_confirm(event, plans_store, chat_client)
        elif function_name == ACTION_PICK_ANOTHER:
            handle_pick_another(event, plans_store, chat_client)
    except Exception:
        logging.exception("Unhandled error in card click handler")
    return {}


@functions_framework.http
def reminder_checker(request):
    _init_singletons()
    from src.reminder.checker import run_reminders
    space_name = os.environ.get("CHAT_SPACE_NAME", "")
    if not space_name:
        return jsonify({"error": "CHAT_SPACE_NAME not set"}), 500
    run_reminders(birthdays_store, plans_store, chat_client, space_name=space_name)
    return jsonify({"status": "ok"}), 200
