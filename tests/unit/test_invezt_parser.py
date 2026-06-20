"""Testes do parser Maia / Invezt PREMIUM."""

from src.invezt.parser import is_invezt_overview, parse_invezt_message

FOREX_SAMPLE = """
Atualização diária — Invezt 📊

📊 OVERVIEW FOREX | 20/06/2026

🌎 Notícia de Destaque:
O mercado segue atento às expectativas de cortes de juros globais.

📈 Melhores Oportunidades do Dia:

🇪🇺 EUR/USD — COMPRA
O euro mantém força compradora.
🇬🇧 GBP/USD — COMPRA
A libra segue positiva.
🇯🇵 USD/JPY — VENDA
O iene ganha força.
🇨🇦 USD/CAD — VENDA
A recuperação das commodities favorece o dólar canadense.

🎯 Resumo Operacional:
✅EUR/USD → Compra
✅ GBP/USD → Compra
✅ USD/JPY → Venda
✅ USD/CAD → Venda
"""

CRYPTO_SAMPLE = """
Abertura do dia — Invezt 📊

📊 Overview Cripto – 20/06/2026

O mercado segue em compasso de espera, com o Bitcoin mantendo suporte.

📰 Principais notícias: • Bitcoin continua resiliente.

🎯 Melhores entradas para observar hoje:
 🪙  BTC – Continua sendo a posição mais defensiva do mercado.
 🪙  ETH – Ethereum segue como principal aposta.
 🪙  SOL – Continua entre as altcoins mais fortes.

⚠️ Estratégia do dia: manter foco em ativos líderes (BTC e ETH).
"""

RANKING_SAMPLE = """
Abertura do dia — Invezt 📊

Overview Cripto — 05 de Junho de 2026

• Viés para hoje:
🟡Neutro para levemente otimista no curto prazo.

🪙 Solana (SOL)
Viés
🟢 Otimista.

🪙 XRP
Viés
🟢 Otimista.

Ranking de melhores oportunidades hoje

1°- Solana 🪙
2°- Ethereum 🔹
3°- Bitcoin 💰
4°- XRP 🪙
"""

CLOSING_SAMPLE = """
🌛 Boa Noite, time da Invezt!

📊 Fechamento do Mercado:
1️⃣ Criptomoedas: • Bitcoin segue trabalhando em uma região decisiva.
💱 Forex: • O dólar continua demonstrando força.
"""


def test_is_invezt_overview_rejects_short_text() -> None:
    assert not is_invezt_overview("invezt")
    assert is_invezt_overview(FOREX_SAMPLE)


def test_parse_forex_overview() -> None:
    briefing = parse_invezt_message(FOREX_SAMPLE)
    assert briefing is not None
    assert briefing.kind == "forex"
    pairs = {p.pair: p.direction for p in briefing.forex_picks}
    assert pairs.get("EUR/USD") == "buy"
    assert pairs.get("GBP/USD") == "buy"
    assert pairs.get("USD/JPY") == "sell"
    assert pairs.get("USD/CAD") == "sell"
    assert briefing.headline is not None
    assert "juros" in briefing.headline.lower() or "mercado" in briefing.headline.lower()


def test_parse_crypto_overview() -> None:
    briefing = parse_invezt_message(CRYPTO_SAMPLE)
    assert briefing is not None
    assert briefing.kind == "crypto"
    symbols = [p.symbol for p in briefing.crypto_picks]
    assert "BTC" in symbols
    assert "ETH" in symbols
    assert "SOL" in symbols


def test_parse_ranking_crypto() -> None:
    briefing = parse_invezt_message(RANKING_SAMPLE)
    assert briefing is not None
    symbols = [p.symbol for p in briefing.crypto_picks]
    assert "SOL" in symbols
    assert "ETH" in symbols
    assert "BTC" in symbols
    assert "XRP" in symbols


def test_parse_closing_message() -> None:
    briefing = parse_invezt_message(CLOSING_SAMPLE)
    assert briefing is not None
    assert briefing.kind == "closing"


def test_non_invezt_returns_none() -> None:
    assert parse_invezt_message("TRADE NOVO #BTCUSDT entrada 65000") is None
