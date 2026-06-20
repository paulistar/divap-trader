"""Testes do parser Financial Move Bot (Tasso)."""

from decimal import Decimal

from src.profiles.loader import load_profile
from src.tasso.signal_parser import (
    classify_alert_text,
    classify_message,
    is_curto_accept_prompt,
    is_long_teaser,
    is_stop_hit_message,
    is_trade_update,
    normalize_tasso_symbol,
    parse_stop_hit,
    parse_trade_details,
    resolve_profile_from_detail,
)

TRADE_NOVO_TEASER = """
💰💰💰 TRADE NOVO 💰💰💰

🔒 Exclusivo p/ VIPs
🎯 Lucro esperado:
Alvo 1: 41.3%
Alvo 2: 54.35%

Clique no botão abaixo para ver os detalhes do trade e estratégia a ser utilizada no bot 👇
"""

STOP_HIT = """
❗ HORA DE PARAR ❗
❌ STOP atingido em #CUSDT
Perda: -19.44% 😔
Tempo: 19 horas e 30 minutos ⏰
"""

PIEVERSE_CURTO = """
💰💰💰 PIEVERSEUSDT (LONG) 💰💰💰

⏰ Postado em: 20/06/2026 11:50:54

💲 Preço bybit: 0.7225
⌚ Atualizado em: 20/06/2026 18:03:56

➡️ Preço para compra: 0.715 - 0.735
➡️ Alocação de patrimônio: 5 %

➡️ Alavancagem: 5

🎯 Bons alvos de venda:
🔜 1ª Zona de venda: 0.789 -  Vender 25% (Lucro 44.14%)
🔜 2ª Zona de venda: 0.85 -  Vender 25% (Lucro 86.21%)
🔜 3ª Zona de venda: 0.98 -  Vender 25% (Lucro 175.86%)
🔜 4ª Zona de venda: 1.25 -  Vender 25% (Lucro 362.07%)

🛑️ Stoploss: 0.69 (-24.14%)

⚠️ Trade mais curto e mais agressivo. Gerencie seu capital adequadamente!
"""

EDGE_LONG = """
💰💰💰 EDGEUSDT (LONG) 💰💰💰

⏰ Postado em: 19/06/2026 20:36:23

💲 Preço bybit: 0.4035
⌚ Atualizado em: 20/06/2026 18:06:09

➡️ Preço para compra: 0.35 - 0.38
➡️ Alocação de patrimônio: 3 %

➡️ Alavancagem: 2

🎯 Bons alvos de venda:
✅ 1ª Zona de venda: 0.43 -  Vender 25% (Lucro 35.62%)
🔜 2ª Zona de venda: 0.69 -  Vender 25% (Lucro 178.08%)
🔜 3ª Zona de venda: 0.95 -  Vender 25% (Lucro 320.55%)
🔜 4ª Zona de venda: 1.29 -  Vender 25% (Lucro 506.85%)

🛑️ Stoploss atualizado: 0.365 (0.0%)
🛑️ Stoploss antigo: 0.32

⚠️ Operações alavancadas são de alto risco, por isso gerencie corretamente sua banca e o STOP da operação
"""


def test_curto_accept_prompt_is_second_step_only() -> None:
    assert is_curto_accept_prompt("Trade curto com alto risco, gerencie muito bem sua mão")
    assert classify_message("Trade curto com alto risco, gerencie muito bem sua mão") is None


def test_classify_trade_curto_teaser() -> None:
    action = classify_message("🔥 TRADE CURTO confirmado agora!", has_detail_button=True)
    assert action is not None
    assert action.action == "request_details"


def test_curto_detail_despite_long_label() -> None:
    profile_id, variant = resolve_profile_from_detail(PIEVERSE_CURTO)
    assert profile_id == "tasso_curto"
    assert variant == "curto"


def test_parse_pieverse_curto_signal() -> None:
    signal = parse_trade_details(
        PIEVERSE_CURTO,
        profile_id="tasso_curto",
        variant="curto",
        symbol_hint="PIEVERSEUSDT",
        direction_hint="buy",
        raw_alert_text=PIEVERSE_CURTO,
    )
    assert signal is not None
    assert signal.profile_id == "tasso_curto"
    assert signal.symbol == "PIEVERSEUSDT"
    assert signal.direction == "buy"
    assert signal.entry_price == Decimal("0.725")
    assert signal.stop_loss == Decimal("0.69")
    assert signal.take_profit_levels == (
        Decimal("0.789"),
        Decimal("0.85"),
        Decimal("0.98"),
        Decimal("1.25"),
    )
    assert signal.allocation_pct == Decimal("5")
    assert signal.leverage == 5
    assert signal.signal_kind == "new"


def test_parse_edge_long_signal() -> None:
    signal = parse_trade_details(
        EDGE_LONG,
        profile_id="tasso_long",
        variant="long",
        symbol_hint="EDGEUSDT",
        direction_hint="buy",
        raw_alert_text=EDGE_LONG,
    )
    assert signal is not None
    assert signal.profile_id == "tasso_long"
    assert signal.symbol == "EDGEUSDT"
    assert signal.entry_price == Decimal("0.365")
    assert signal.stop_loss == Decimal("0.365")
    assert signal.targets_hit == 1
    assert is_trade_update(EDGE_LONG)
    assert signal.signal_kind == "update"


def test_classify_long_teaser() -> None:
    assert is_long_teaser(TRADE_NOVO_TEASER)
    action = classify_message(TRADE_NOVO_TEASER, has_detail_button=True)
    assert action is not None
    assert action.action == "request_details"


def test_passive_new_detail_not_classified() -> None:
    assert classify_message(PIEVERSE_CURTO) is None


def test_parse_stop_hit_message() -> None:
    assert is_stop_hit_message(STOP_HIT)
    signal = parse_stop_hit(STOP_HIT)
    assert signal is not None
    assert signal.signal_kind == "stop_hit"
    assert signal.symbol == normalize_tasso_symbol("CUSDT")


def test_classify_long_full_message() -> None:
    action = classify_message(EDGE_LONG)
    assert action is not None
    assert action.action == "parse_detail"
    assert action.profile_id == "tasso_long"
    assert action.symbol_hint == "EDGEUSDT"


def test_tasso_profiles_in_binance_list() -> None:
    from src.profiles.loader import load_binance_profiles

    ids = {p.id for p in load_binance_profiles()}
    assert "tasso_curto" in ids
    assert "tasso_long" in ids
    assert "otc" not in ids


def test_tasso_profile_kind() -> None:
    curto = load_profile("tasso_curto")
    long_p = load_profile("tasso_long")
    assert curto is not None and curto.kind == "tasso"
    assert long_p is not None and long_p.kind == "tasso"
    assert curto.scan.enabled is False
    assert long_p.scan.enabled is False
