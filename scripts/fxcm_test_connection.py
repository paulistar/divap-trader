#!/usr/bin/env python3
"""Test FXCM API connection using FXCM_ACCESS_TOKEN from environment."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings
from src.markets.fxcm_client import fxcm_configured, get_fxcm_connection, reset_fxcm_connection
from src.data.sources.fxcm import FxcmSource


def main() -> int:
    if not fxcm_configured():
        print(
            "FXCM_ACCESS_TOKEN não definido.\n\n"
            "Como obter:\n"
            "1. Acesse https://tradingstation.fxcm.com/ (login demo)\n"
            "2. User Account → Token Management → Create Token\n"
            "3. Copie o token e defina no Easypanel:\n"
            "   FXCM_ACCESS_TOKEN=seu_token_aqui\n"
            "   FXCM_SERVER=demo\n"
        )
        return 1

    reset_fxcm_connection()
    try:
        con = get_fxcm_connection()
        print(f"Contas: {con.account_ids}")
        print(f"Instrumentos (amostra): {con.get_instruments()[:5]}...")

        source = FxcmSource()
        candles = source.fetch_ohlcv("EUR_USD", "1h", limit=5)
        print(f"Candles EUR/USD 1h: {len(candles)}")
        if candles:
            last = candles[-1]
            print(f"  Último: {last.timestamp} close={last.close}")

        balance = con.get_accounts_summary(kind="dict")
        print(f"Resumo conta: {balance}")
        print("\nOK — FXCM conectada.")
        return 0
    except Exception as exc:
        print(f"ERRO: {exc}")
        print(
            "\nSe o token foi criado agora, aguarde alguns minutos ou envie e-mail para "
            "api@fxcm.com com seu username (701913665) pedindo ativação REST API."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
