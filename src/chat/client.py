import os
from googleapiclient.discovery import build
import google.auth


def build_chat_service():
    """Build an authenticated Google Chat API service using Application Default Credentials."""
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/chat.bot"])
    return build("chat", "v1", credentials=creds)


class ChatClient:
    def __init__(self, service):
        self.service = service

    def post_message(self, space_name: str, text: str = None, card: dict = None) -> dict:
        """Post a text or card message to a space. Returns the created message resource."""
        body = {}
        if text:
            body["text"] = text
        if card:
            body.update(card)
        return (
            self.service.spaces()
            .messages()
            .create(parent=space_name, body=body)
            .execute()
        )

    def update_message(self, message_name: str, card: dict, update_mask: str = "cardsV2") -> dict:
        """Edit an existing message (card update)."""
        return (
            self.service.spaces()
            .messages()
            .patch(
                name=message_name,
                updateMask=update_mask,
                body=card,
            )
            .execute()
        )

    def get_space_members(self, space_name: str) -> list[str]:
        """Return list of human member user resource names (bots excluded)."""
        return [m["name"] for m in self.get_space_members_with_names(space_name)]

    def get_space_members_with_names(self, space_name: str) -> list[dict]:
        """Return list of {"name": ..., "displayName": ...} for human members only."""
        resp = (
            self.service.spaces()
            .members()
            .list(parent=space_name)
            .execute()
        )
        return [
            {"name": m["member"]["name"], "displayName": m["member"].get("displayName", "")}
            for m in resp.get("memberships", [])
            if m.get("member", {}).get("type") == "HUMAN"
        ]
