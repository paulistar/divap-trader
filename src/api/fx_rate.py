"""Cotação USD/BRL para exibição no painel OTC."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx

from src.core.exceptions import ExchangeError


async def _fetch_frankfurter() -> Decimal:
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(
            "https://api.frankfurter.app/latest",
            params={"from": "USD", "to": "BRL"},
        )
        response.raise_for_status()
        rate = response.json().get("rates", {}).get("BRL")
        if rate is None:
            raise ExchangeError("Frankfurter não retornou USD/BRL")
        return Decimal(str(rate))


async def _fetch_awesomeapi() -> Decimal:
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get("https://economia.awesomeapi.com.br/json/last/USD-BRL")
        response.raise_for_status()
        payload = response.json().get("USDBRL") or {}
        bid = payload.get("bid") or payload.get("ask")
        if not bid:
            raise ExchangeError("AwesomeAPI não retornou USD/BRL")
        return Decimal(str(bid))


async def fetch_usd_brl_rate() -> tuple[Decimal, str, datetime]:
    """Retorna (taxa, fonte, timestamp UTC)."""
    errors: list[str] = []
    for fetcher, source in (
        (_fetch_frankfurter, "Frankfurter"),
        (_fetch_awesomeapi, "AwesomeAPI"),
    ):
        try:
            rate = await fetcher()
            if rate > 0:
                return rate, source, datetime.now(UTC)
        except Exception as exc:  # noqa: BLE001 — tenta próxima fonte
            errors.append(f"{source}: {exc}")
    detail = "; ".join(errors) if errors else "sem detalhe"
    raise ExchangeError(f"Não foi possível obter cotação USD/BRL ({detail})")
