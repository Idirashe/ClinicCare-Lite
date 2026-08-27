"""
backend/models/message.py

Message model — secure, non-urgent messaging between patient and
clinician. Stored in messages.json.

Reminder (Section 6 of spec): this channel is NOT for urgent/emergency
communication. Any messaging UI built on this must show a persistent
reminder of that.

TODO (Member 3 / Messaging lead): build the chat-style UI and, if going
the Flask route, wire up WebSockets (or simple polling) for near-real-time
updates.
"""
import uuid
from datetime import datetime
from backend.storage import load_json, save_json

MESSAGES_FILE = "messages.json"


class Message:
    def __init__(self, message_id, sender_id, recipient_id, content,
                 timestamp=None, is_broadcast=False):
        self.message_id = message_id
        self.sender_id = sender_id
        self.recipient_id = recipient_id  # None/"ALL" if is_broadcast
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()
        self.is_broadcast = is_broadcast

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def send(sender_id, recipient_id, content, is_broadcast=False):
        messages = load_json(MESSAGES_FILE)
        message = Message(
            message_id=str(uuid.uuid4())[:8],
            sender_id=sender_id,
            recipient_id=recipient_id,
            content=content,
            is_broadcast=is_broadcast,
        )
        messages.append(message.to_dict())
        save_json(MESSAGES_FILE, messages)
        return message

    @staticmethod
    def conversation(user_a_id, user_b_id):
        """All messages exchanged between two specific users, oldest first."""
        messages = load_json(MESSAGES_FILE)
        convo = [
            m for m in messages
            if {m["sender_id"], m["recipient_id"]} == {user_a_id, user_b_id}
        ]
        return sorted(convo, key=lambda m: m["timestamp"])

    @staticmethod
    def inbox_for(user_id):
        """Everything a user has received, including broadcasts."""
        messages = load_json(MESSAGES_FILE)
        return [
            m for m in messages
            if m["recipient_id"] == user_id or m.get("is_broadcast")
        ]
