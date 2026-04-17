from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from scavenger.userbot import KeyboxScavengerUserbot


class FakeClient:
    def __init__(self):
        self.registered_handlers = []

    def on(self, event_builder):
        def decorator(handler):
            self.registered_handlers.append((handler, event_builder))
            return handler

        return decorator


class KeyboxScavengerUserbotTests(unittest.TestCase):
    def test_registers_handlers_for_new_and_edited_messages(self):
        settings = Mock()
        validator = Mock()
        storage = Mock()
        userbot = KeyboxScavengerUserbot(settings=settings, validator=validator, storage=storage)
        client = FakeClient()
        userbot._handle_message = AsyncMock()

        userbot._register_handlers(client, [12345, "test-channel"])

        self.assertEqual(len(client.registered_handlers), 2)
        first_handler, first_builder = client.registered_handlers[0]
        second_handler, second_builder = client.registered_handlers[1]

        self.assertEqual(first_builder.__class__.__name__, "NewMessage")
        self.assertEqual(second_builder.__class__.__name__, "MessageEdited")

        fake_event = object()
        asyncio.run(first_handler(fake_event))
        asyncio.run(second_handler(fake_event))

        self.assertEqual(userbot._handle_message.await_count, 2)
        userbot._handle_message.assert_any_await(fake_event)


if __name__ == "__main__":
    unittest.main()
