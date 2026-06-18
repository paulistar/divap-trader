#!/usr/bin/env python3
"""Test IQ Option connection using IQOPTION_EMAIL / IQOPTION_PASSWORD from environment."""

from __future__ import annotations

import sys

from src.otc.iqoption_client import fetch_iqoption_balance, iqoption_configured, reset_iqoption_client
from src.otc.service import build_otc_status


def main() -> int:
    if not iqoption_configured():
        print(
            "IQOPTION_EMAIL e IQOPTION_PASSWORD não definidos.\n\n"
            "Configure no .env ou Easypanel:\n"
            "  IQOPTION_EMAIL=seu@email.com\n"
            "  IQOPTION_PASSWORD=sua_senha\n"
            "  IQOPTION_ACCOUNT_MODE=PRACTICE\n"
        )
        return 1

    try:
        reset_iqoption_client()
        balance = fetch_iqoption_balance()
        status = build_otc_status()
        print(f"OK — IQ Option conectada (modo {status['account_mode']})")
        print(f"Saldo demo/prática: ${balance}")
        print(f"OTC dry_run: {status['dry_run']}")
        print(f"OTC trading enabled: {status['otc_trading_enabled']}")
        return 0
    except Exception as exc:
        print(f"ERRO — {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
