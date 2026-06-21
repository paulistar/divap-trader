"""Helpers de agregação por período para o painel OTC (IQ Option).

Todas as expressões SQL operam sobre uma coluna ``TIMESTAMPTZ`` convertida
para o fuso local informado (default America/Sao_Paulo) para que a
classificação por dia/semana/mês reflita o horário do operador.
"""

from __future__ import annotations

VALID_PERIODS: tuple[str, ...] = (
    "day",
    "week",
    "month",
    "quarter",
    "semester",
    "year",
)

PERIOD_LABELS: dict[str, str] = {
    "day": "Dia",
    "week": "Semana",
    "month": "Mês",
    "quarter": "Trimestre",
    "semester": "Semestre",
    "year": "Ano",
}

DEFAULT_TIMEZONE = "America/Sao_Paulo"


def normalize_period(period: str | None) -> str:
    """Valida o período pedido, caindo para ``day`` quando inválido."""
    value = (period or "").strip().lower()
    return value if value in VALID_PERIODS else "day"


def _local(column: str, timezone: str) -> str:
    return f"({column} AT TIME ZONE '{timezone}')"


def bucket_expr(period: str, column: str, timezone: str = DEFAULT_TIMEZONE) -> str:
    """Expressão SQL que trunca ``column`` no início do bucket do período.

    Postgres não tem ``date_trunc('semester', ...)``; calculamos manualmente
    a partir do início do ano + offset de 6 meses.
    """
    period = normalize_period(period)
    local = _local(column, timezone)
    if period == "semester":
        return (
            f"(date_trunc('year', {local}) + "
            f"(floor((extract(month from {local})::int - 1) / 6) * interval '6 months'))"
        )
    return f"date_trunc('{period}', {local})"


def same_period_as_ref(
    period: str, column: str, timezone: str = DEFAULT_TIMEZONE
) -> str:
    """True quando ``column`` cai no mesmo bucket de período que o timestamp ``%s``."""
    col_bucket = bucket_expr(period, column, timezone)
    local = f"(%s::timestamptz AT TIME ZONE '{timezone}')"
    if period == "semester":
        ref_bucket = (
            f"(date_trunc('year', {local}) + "
            f"(floor((extract(month from {local})::int - 1) / 6) * interval '6 months'))"
        )
    else:
        ref_bucket = f"date_trunc('{period}', {local})"
    return f"{col_bucket} = {ref_bucket}"


def current_period_predicate(period: str, column: str, timezone: str = DEFAULT_TIMEZONE) -> str:
    """Filtro SQL booleano que isola o período corrente (hoje/semana atual/...)."""
    period = normalize_period(period)
    return f"{bucket_expr(period, column, timezone)} = {bucket_expr(period, 'NOW()', timezone)}"
