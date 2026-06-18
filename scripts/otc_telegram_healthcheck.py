#!/usr/bin/env python3
"""Healthcheck do listener OTC Telegram.

Sai 0 se o heartbeat no Redis for recente, 1 caso contrário.
Usado pelo HEALTHCHECK do container otc-telegram + autoheal.
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from src.otc.heartbeat import listener_is_alive

        return 0 if listener_is_alive() else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
