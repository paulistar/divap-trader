"""Lista grupos/canais recentes para configurar OTC_TELEGRAM_CHAT_ID."""

from __future__ import annotations

import asyncio
import os
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session = os.environ["TELEGRAM_USER_SESSION"]

    client = TelegramClient(StringSession(session), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("Sessão não autorizada.", file=sys.stderr)
        sys.exit(1)

    print("id\tname\ttype")
    async for dialog in client.iter_dialogs(limit=100):
        entity = dialog.entity
        kind = type(entity).__name__
        print(f"{dialog.id}\t{dialog.name}\t{kind}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
