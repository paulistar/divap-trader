#!/usr/bin/env python3
"""Gera TELEGRAM_USER_SESSION para o listener OTC (modo user / Telethon).

Uso local (interativo — pede código SMS):
  python scripts/telegram_create_session.py

Saída: string de sessão para colar em TELEGRAM_USER_SESSION no Easypanel.
Obtenha api_id e api_hash em https://my.telegram.org/apps
"""

from __future__ import annotations

import os
import sys

from telethon.sync import TelegramClient
from telethon.sessions import StringSession


def main() -> None:
    api_id_raw = os.environ.get("TELEGRAM_API_ID") or input("TELEGRAM_API_ID: ").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH") or input("TELEGRAM_API_HASH: ").strip()
    if not api_id_raw or not api_hash:
        print("api_id e api_hash são obrigatórios", file=sys.stderr)
        sys.exit(1)

    api_id = int(api_id_raw)
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session = client.session.save()
    print("\nCole no Easypanel → Environment:\n")
    print(f"TELEGRAM_USER_SESSION={session}")


if __name__ == "__main__":
    main()
