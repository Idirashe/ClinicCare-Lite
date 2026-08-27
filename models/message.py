"""
Message model for ClinicCare-Lite.

Handles non-urgent secure messaging between a patient and their
clinician, plus clinic-wide announcements.

IMPORTANT: the UI (not this file) must show a persistent notice that
this channel is NOT monitored continuously and must NOT be used for
emergencies 

Owned by: Jolene (Clinician Services & Messaging lead)
"""

import json
import os
from datetime import datetime

MESSAGES_FILE = os.path.join("data", "messages.json")


class Message:
    def __init__(self, sender_id, recipient_id, content, is_announcement=False):
        """
        sender_id / recipient_id: user_ids of who's talking
        content: the message text
        is_announcement: True if this is a clinic-wide broadcast rather
                          than a private 1-to-1 message (recipient_id
                          would be a clinic_id in that case, not a
                          single patient)
        """
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.content = content
        self.is_announcement = is_announcement
        self.timestamp = datetime.now().isoformat()
        self.read = False

    def save(self):
        """
        Append this message onto the message list in messages.json.
        Messages are stored as a JSON list (not a dict like users),
        because there's no natural unique ID for a message other than
        "the next one in the list" - order matters for conversations.
        """
        with open(MESSAGES_FILE, "r+") as f:
            data = json.load(f)  # this is a list, e.g. []
            data.append({
                "sender_id": self.sender_id,
                "recipient_id": self.recipient_id,
                "content": self.content,
                "is_announcement": self.is_announcement,
                "timestamp": self.timestamp,
                "read": self.read,
            })
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=4)

    @staticmethod
    def get_conversation(user_a_id, user_b_id):
        """
        Return every message exchanged between two specific users, in
        chronological order. This powers the 1-to-1 chat view.

        SECURITY NOTE: this function only returns messages where BOTH
        IDs match - a patient calling this can never accidentally pull
        back another patient's conversation, because that conversation
        simply won't match the (sender, recipient) pair being asked for.
        Still, always call this with an ID pulled from the LOGGED-IN
        SESSION, never from a value typed into a URL or form field.
        """
        with open(MESSAGES_FILE, "r") as f:
            data = json.load(f)

        conversation = [
            msg for msg in data
            if not msg["is_announcement"] and (
                (msg["sender_id"] == user_a_id and msg["recipient_id"] == user_b_id) or
                (msg["sender_id"] == user_b_id and msg["recipient_id"] == user_a_id)
            )
        ]
        # Sort oldest-first so the chat reads top-to-bottom naturally.
        conversation.sort(key=lambda m: m["timestamp"])
        return conversation

    @staticmethod
    def get_announcements(clinic_id):
        """
        Return all clinic-wide announcements for a given clinic, newest
        first, so patients see the latest notice at the top of their
        dashboard.
        """
        with open(MESSAGES_FILE, "r") as f:
            data = json.load(f)

        announcements = [
            msg for msg in data
            if msg["is_announcement"] and msg["recipient_id"] == clinic_id
        ]
        announcements.sort(key=lambda m: m["timestamp"], reverse=True)
        return announcements
