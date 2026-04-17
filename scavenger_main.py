import asyncio
import sys

from dotenv import load_dotenv
from loguru import logger

from scavenger.config import load_settings
from scavenger.storage import KeyboxStorage
from scavenger.userbot import KeyboxScavengerUserbot
from scavenger.validator import KeyboxValidator


def configure_logging(log_level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=log_level)


async def main() -> None:
    load_dotenv()
    settings = load_settings()
    configure_logging(settings.log_level.upper())

    storage = KeyboxStorage(settings.output_dir)
    validator = KeyboxValidator(settings)
    userbot = KeyboxScavengerUserbot(settings=settings, validator=validator, storage=storage)

    logger.info("Starting keybox scavenger")
    await userbot.run()


if __name__ == "__main__":
    asyncio.run(main())
