from __future__ import annotations

import unittest
from unittest.mock import Mock

from scavenger.userbot import KeyboxScavengerUserbot


class FakeClient:
    def __init__(self):
        self.registered_handlers = []

    def add_event_handler(self, handler, event_builder):
        self.registered_handlers.append((handler, event_builder))


class KeyboxScavengerUserbotTests(unittest.TestCase):
    def test_registers_handlers_for_new_and_edited_messages(self):
        settings = Mock()
        validator = Mock()
        storage = Mock()
        userbot = KeyboxScavengerUserbot(settings=settings, validator=validator, storage=storage)
        client = FakeClient()

        userbot._register_handlers(client, [12345, "test-channel"])

        self.assertEqual(len(client.registered_handlers), 2)
        first_handler, first_builder = client.registered_handlers[0]
        second_handler, second_builder = client.registered_handlers[1]

        self.assertIs(first_handler.__self__, userbot)
        self.assertIs(second_handler.__self__, userbot)
        self.assertIs(first_handler.__func__, userbot._handle_message.__func__)
        self.assertIs(second_handler.__func__, userbot._handle_message.__func__)
        self.assertEqual(first_builder.__class__.__name__, "NewMessage")
        self.assertEqual(second_builder.__class__.__name__, "MessageEdited")


if __name__ == "__main__":
    unittest.main()
