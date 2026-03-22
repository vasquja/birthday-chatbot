from unittest.mock import MagicMock, patch
import pytest
from src.chat.client import ChatClient


@pytest.fixture
def client():
    service = MagicMock()
    return ChatClient(service)


def test_post_message_text(client):
    client.service.spaces.return_value.messages.return_value.create.return_value.execute.return_value = {
        "name": "spaces/AAA/messages/BBB"
    }
    result = client.post_message("spaces/AAA", text="Hello!")
    assert result["name"] == "spaces/AAA/messages/BBB"
    client.service.spaces.return_value.messages.return_value.create.assert_called_once()
    call_kwargs = client.service.spaces.return_value.messages.return_value.create.call_args
    assert call_kwargs.kwargs["body"]["text"] == "Hello!"


def test_post_message_card(client):
    card = {"cardsV2": [{"cardId": "test"}]}
    client.service.spaces.return_value.messages.return_value.create.return_value.execute.return_value = {
        "name": "spaces/AAA/messages/CCC"
    }
    client.post_message("spaces/AAA", card=card)
    call_kwargs = client.service.spaces.return_value.messages.return_value.create.call_args
    assert "cardsV2" in call_kwargs.kwargs["body"]


def test_update_message(client):
    client.service.spaces.return_value.messages.return_value.patch.return_value.execute.return_value = {}
    client.update_message("spaces/AAA/messages/BBB", {"cardsV2": []})
    client.service.spaces.return_value.messages.return_value.patch.assert_called_once()


def test_get_space_members(client):
    client.service.spaces.return_value.members.return_value.list.return_value.execute.return_value = {
        "memberships": [
            {"member": {"name": "users/123", "displayName": "Jason", "type": "HUMAN"}},
            {"member": {"name": "users/456", "displayName": "Mike", "type": "HUMAN"}},
            {"member": {"name": "users/BOT", "displayName": "Bot", "type": "BOT"}},
        ]
    }
    # get_space_members returns just user resource names (bots filtered)
    members = client.get_space_members("spaces/AAA")
    assert members == ["users/123", "users/456"]


def test_get_space_members_with_names(client):
    client.service.spaces.return_value.members.return_value.list.return_value.execute.return_value = {
        "memberships": [
            {"member": {"name": "users/123", "displayName": "Jason", "type": "HUMAN"}},
            {"member": {"name": "users/456", "displayName": "Mike", "type": "HUMAN"}},
            {"member": {"name": "users/BOT", "displayName": "Bot", "type": "BOT"}},
        ]
    }
    members = client.get_space_members_with_names("spaces/AAA")
    assert members == [
        {"name": "users/123", "displayName": "Jason"},
        {"name": "users/456", "displayName": "Mike"},
    ]
