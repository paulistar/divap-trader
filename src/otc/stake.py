"""Cálculo de entrada e limites diários a partir da banca de referência."""

from __future__ import annotations

from decimal import Decimal

VALID_RISK_PROFILES: tuple[str, ...] = ("conservative", "moderate", "aggressive")
DEFAULT_RISK_PROFILE = "moderate"

# Multiplicador do pior ciclo martingale (2,2×, 2 proteções): L0 + P1 + P2
MARTINGALE_CYCLE_MULTIPLIER = Decimal("8.04")

# Pacotes alinhados à gestão profissional:
# - Entrada = risco por operação (faixas Switch Markets / FX Foundations)
# - Stop loss diário ≈ 2–3× entrada (Zaya Capital, DayTradingToolkit)
# - Stop win diário ≈ 1,3–1,7× entrada (trava ganho assimétrico, Tradicted)
# - Tetos de stop loss respeitam faixa diária por perfil (Switch: 0,5–1% / 1–2% / 3–5%)
RISK_PROFILES: dict[str, dict[str, object]] = {
    "conservative": {
        "label": "Conservador",
        "range_label": "0,5% – 1%",
        "stop_loss_range_label": "2% do dia",
        "stop_win_range_label": "1,2% do dia",
        "description": "Máxima segurança — entrada baixa, stops apertados (~2,7× a entrada).",
        "stake_pct": Decimal("0.75"),
        "daily_stop_loss_pct": Decimal("2.0"),
        "daily_stop_win_pct": Decimal("1.2"),
        "pct_min": Decimal("0.5"),
        "pct_max": Decimal("1"),
    },
    "moderate": {
        "label": "Moderado",
        "range_label": "1% – 2%",
        "stop_loss_range_label": "3% do dia",
        "stop_win_range_label": "2% do dia",
        "description": "Padrão industry — stop loss = 2× entrada (regra dos 3 níveis).",
        "stake_pct": Decimal("1.5"),
        "daily_stop_loss_pct": Decimal("3.0"),
        "daily_stop_win_pct": Decimal("2.0"),
        "pct_min": Decimal("1"),
        "pct_max": Decimal("2"),
    },
    "aggressive": {
        "label": "Agressivo",
        "range_label": "2% – 3%",
        "stop_loss_range_label": "5% do dia",
        "stop_win_range_label": "3,5% do dia",
        "description": "Teto agressivo do mercado (3–5% dia) — drawdown sobe rápido.",
        "stake_pct": Decimal("2.5"),
        "daily_stop_loss_pct": Decimal("5.0"),
        "daily_stop_win_pct": Decimal("3.5"),
        "pct_min": Decimal("2"),
        "pct_max": Decimal("3"),
    },
}


def normalize_risk_profile(value: str | None) -> str:
    profile = (value or "").strip().lower()
    return profile if profile in VALID_RISK_PROFILES else DEFAULT_RISK_PROFILE


def stake_pct_for_profile(profile: str) -> Decimal:
    key = normalize_risk_profile(profile)
    return RISK_PROFILES[key]["stake_pct"]  # type: ignore[return-value]


def stop_pcts_for_profile(profile: str) -> tuple[Decimal, Decimal]:
    """Retorna (stop_win_pct, stop_loss_pct) do pacote do perfil."""
    key = normalize_risk_profile(profile)
    meta = RISK_PROFILES[key]
    return meta["daily_stop_win_pct"], meta["daily_stop_loss_pct"]  # type: ignore[return-value]


def worst_cycle_loss_pct(stake_pct: Decimal) -> Decimal:
    """Pior perda de um ciclo completo L0+P1+P2 em % da banca."""
    return (stake_pct * MARTINGALE_CYCLE_MULTIPLIER).quantize(Decimal("0.01"))


def resolve_profile_limits(profile: str) -> dict[str, Decimal]:
    """Pacote completo entrada + stops para um perfil."""
    key = normalize_risk_profile(profile)
    meta = RISK_PROFILES[key]
    stake_pct: Decimal = meta["stake_pct"]  # type: ignore[assignment]
    stop_win: Decimal = meta["daily_stop_win_pct"]  # type: ignore[assignment]
    stop_loss: Decimal = meta["daily_stop_loss_pct"]  # type: ignore[assignment]
    return {
        "stake_pct": stake_pct,
        "daily_stop_win_pct": stop_win,
        "daily_stop_loss_pct": stop_loss,
        "worst_cycle_loss_pct": worst_cycle_loss_pct(stake_pct),
    }


def stake_max_usd_for_profile(reference_balance_usd: Decimal, profile: str) -> Decimal:
    """Teto = limite superior da faixa do perfil × banca do dia."""
    key = normalize_risk_profile(profile)
    pct_max: Decimal = RISK_PROFILES[key]["pct_max"]  # type: ignore[assignment]
    return (reference_balance_usd * pct_max / Decimal("100")).quantize(Decimal("0.01"))


def resolve_stake_from_settings(
    reference_balance_usd: Decimal,
    *,
    stake_risk_profile: str | None,
    stake_pct: Decimal | None = None,
    stake_min_usd: Decimal | None = None,
    stake_max_usd: Decimal | None = None,
) -> tuple[Decimal, str]:
    """Retorna (stake_pct efetivo, perfil usado)."""
    profile = normalize_risk_profile(stake_risk_profile)
    effective_pct = stake_pct if stake_pct and stake_pct > 0 else stake_pct_for_profile(profile)
    return effective_pct, profile


def resolve_daily_base_stake(
    reference_balance_usd: Decimal,
    *,
    stake_pct: Decimal,
    stake_min_usd: Decimal,
    stake_max_usd: Decimal,
) -> Decimal:
    """Entrada L0 = % da banca de referência, com piso e teto."""
    if reference_balance_usd <= 0:
        raise ValueError("reference_balance_usd must be positive")
    raw = reference_balance_usd * stake_pct / Decimal("100")
    clamped = max(stake_min_usd, min(stake_max_usd, raw))
    return clamped.quantize(Decimal("0.01"))


def compute_session_limits(
    reference_balance_usd: Decimal,
    *,
    stake_pct: Decimal,
    stake_min_usd: Decimal,
    stake_max_usd: Decimal,
    daily_stop_win_pct: Decimal,
    daily_stop_loss_pct: Decimal,
) -> dict[str, Decimal]:
    """Deriva entrada e stops fixos do dia a partir da banca snapshot."""
    base_stake = resolve_daily_base_stake(
        reference_balance_usd,
        stake_pct=stake_pct,
        stake_min_usd=stake_min_usd,
        stake_max_usd=stake_max_usd,
    )
    stop_win = (reference_balance_usd * daily_stop_win_pct / Decimal("100")).quantize(
        Decimal("0.01")
    )
    stop_loss = (reference_balance_usd * daily_stop_loss_pct / Decimal("100")).quantize(
        Decimal("0.01")
    )
    return {
        "reference_balance_usd": reference_balance_usd,
        "base_stake_usd": base_stake,
        "stop_win_usd": stop_win,
        "stop_loss_usd": stop_loss,
    }


def risk_profiles_for_api() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key, meta in RISK_PROFILES.items():
        stake_pct: Decimal = meta["stake_pct"]  # type: ignore[assignment]
        items.append(
            {
                "id": key,
                "label": str(meta["label"]),
                "range_label": str(meta["range_label"]),
                "description": str(meta["description"]),
                "stake_pct": str(stake_pct),
                "daily_stop_loss_pct": str(meta["daily_stop_loss_pct"]),
                "daily_stop_win_pct": str(meta["daily_stop_win_pct"]),
                "stop_loss_range_label": str(meta["stop_loss_range_label"]),
                "stop_win_range_label": str(meta["stop_win_range_label"]),
                "worst_cycle_loss_pct": str(worst_cycle_loss_pct(stake_pct)),
            }
        )
    return items
