#!/usr/bin/env python3
"""Test IQ Option OTC connection (MCP token preferred, legacy email/password fallback)."""

from __future__ import annotations

import sys

from src.otc.iqoption_client import fetch_iqoption_balance, iqoption_configured, otc_transport
from src.otc.iqoption_client import reset_iqoption_client
from src.otc.mcp_client import mcp_configured
from src.otc.service import build_otc_status


def main() -> int:
    if not iqoption_configured():
        print(
            "IQ Option não configurada.\n\n"
            "Recomendado (MCP oficial, sem SMS):\n"
            "  IQOPTION_MCP_TOKEN=seu_token\n"
            "  IQOPTION_MCP_URL=https://digital-options.mcp.iqoption.com\n"
            "  IQOPTION_ACCOUNT_MODE=PRACTICE\n\n"
            "Alternativa legada (pode exigir 2FA SMS):\n"
            "  IQOPTION_EMAIL=seu@email.com\n"
            "  IQOPTION_PASSWORD=sua_senha\n"
        )
        return 1

    try:
        reset_iqoption_client()
        balance = fetch_iqoption_balance()
        status = build_otc_status()
        transport = otc_transport() or "unknown"
        print(f"OK — IQ Option conectada via {transport} (modo {status['account_mode']})")
        if mcp_configured():
            print(f"MCP mode: {status.get('mcp_mode') or 'n/a'}")
        print(f"Saldo: ${balance}")
        print(f"OTC dry_run: {status['dry_run']}")
        print(f"OTC trading enabled: {status['otc_trading_enabled']}")
        return 0
    except Exception as exc:
        print(f"ERRO — {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
