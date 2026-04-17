from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from scavenger.config import ScavengerSettings
from scavenger.storage import KeyboxStorage
from scavenger.validator import KeyboxValidator
from scavenger.xml_normalizer import XmlNormalizationError, normalize_xml_payload

XML_MIME_TYPES = {"application/xml", "text/xml"}


@dataclass
class ScanStats:
    scanned: int = 0
    valid: int = 0
    invalid: int = 0
    skipped_non_xml: int = 0
    skipped_oversized: int = 0
    errors: int = 0


class KeyboxScavengerUserbot:
    def __init__(
        self,
        settings: ScavengerSettings,
        validator: KeyboxValidator,
        storage: KeyboxStorage,
    ):
        self.settings = settings
        self.validator = validator
        self.storage = storage
        self.stats = ScanStats()

    async def run(self) -> None:
        session = (
            StringSession(self.settings.session_string)
            if self.settings.session_string
            else self.settings.session_name
        )

        client = TelegramClient(
            session=session,
            api_id=self.settings.api_id,
            api_hash=self.settings.api_hash,
            request_retries=max(self.settings.network_retries, 1),
            connection_retries=max(self.settings.network_retries, 1),
            retry_delay=2,
        )

        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError(
                "The Telegram session is not authorized. Set SCAVENGER_SESSION_STRING or use an authorized session file."
            )

        targets = await self._resolve_targets(client)
        if not targets:
            raise RuntimeError("No target chats resolved from SCAVENGER_TARGETS")

        logger.info("Watching {} targets", len(targets))

        @client.on(events.NewMessage(chats=targets))
        async def on_message(event):
            await self._handle_message(event)

        await client.run_until_disconnected()

    async def _resolve_targets(self, client: TelegramClient) -> list:
        resolved = []
        for target in self.settings.monitored_targets:
            try:
                resolved_target = await client.get_input_entity(target)
                resolved.append(resolved_target)
                logger.info("Resolved target {}", target)
            except Exception as exc:
                self.stats.errors += 1
                logger.error("Failed to resolve target {}: {}", target, exc)
        return resolved

    async def _handle_message(self, event) -> None:
        message = event.message
        file_info = message.file
        if file_info is None:
            return

        mime_type = (file_info.mime_type or "").lower()
        file_name = (file_info.name or "").lower()

        is_xml = mime_type in XML_MIME_TYPES or file_name.endswith(".xml")
        if not is_xml:
            self.stats.skipped_non_xml += 1
            return

        file_size = file_info.size or 0
        if file_size > self.settings.max_xml_size:
            self.stats.skipped_oversized += 1
            logger.warning(
                "Skipping oversized XML chat={} message={} size={}",
                event.chat_id,
                message.id,
                file_size,
            )
            return

        try:
            payload = await event.client.download_media(message, bytes)
        except Exception as exc:
            self.stats.errors += 1
            logger.error(
                "Failed to download document chat={} message={}: {}",
                event.chat_id,
                message.id,
                exc,
            )
            return

        if payload is None:
            self.stats.errors += 1
            logger.error(
                "Download returned no payload chat={} message={}",
                event.chat_id,
                message.id,
            )
            return

        xml_payload = bytes(payload)
        try:
            normalized_xml_payload = normalize_xml_payload(xml_payload)
        except XmlNormalizationError as exc:
            logger.warning(
                "Skipping XML normalization chat={} message={} reason={}",
                event.chat_id,
                message.id,
                exc,
            )
            normalized_xml_payload = xml_payload

        self.stats.scanned += 1

        try:
            result = await self.validator.validate(normalized_xml_payload)
        except Exception as exc:
            self.stats.errors += 1
            logger.error(
                "Validation failed chat={} message={}: {}",
                event.chat_id,
                message.id,
                exc,
            )
            return

        if not result.is_valid:
            self.stats.invalid += 1
            logger.info(
                "Rejected keybox chat={} message={} reasons={}",
                event.chat_id,
                message.id,
                "; ".join(result.reasons) if result.reasons else "unknown",
            )
            return

        storage_result = self.storage.persist(normalized_xml_payload)
        self.stats.valid += 1
        logger.info(
            "Stored valid keybox chat={} message={} sha={} new={} latest={}",
            event.chat_id,
            message.id,
            storage_result.digest,
            storage_result.wrote_sha_file,
            storage_result.latest_path,
        )
