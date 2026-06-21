#!/usr/bin/env python3
"""Simulação retroativa OTC: real vs gale multiplier vs recovery vs sem gale.

Uso:
  DATABASE_URL=postgresql://... python scripts/simulate_otc_ladder.py
  python scripts/simulate_otc_ladder.py --payoff 87 --output report.md
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

from src.data.repositories.trade_repo import TradeRepository
from src.otc.simulation import (
    DEFAULT_MULTIPLIER,
    DEFAULT_PAYOFF,
    SimulationStrategy,
    count_outcomes,
    format_simulation_report,
    group_otc_cycles,
    leg_from_row,
    summarize_strategy,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulação retroativa de ladder OTC (real vs recovery vs sem gale)",
    )
    parser.add_argument(
        "--payoff",
        type=Decimal,
        default=DEFAULT_PAYOFF * 100,
        help="Payoff default em %% quando não houver win observado (default: 87)",
    )
    parser.add_argument(
        "--multiplier",
        type=Decimal,
        default=DEFAULT_MULTIPLIER,
        help="Multiplicador do cenário gale atual (default: 2.2)",
    )
    parser.add_argument(
        "--recovery-target",
        type=Decimal,
        default=Decimal("0"),
        help="Lucro alvo por ciclo no recovery em US$ (default: 0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10_000,
        help="Máximo de pernas fechadas a carregar (default: 10000)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Salvar relatório markdown neste arquivo (default: stdout)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://divap:divap@localhost:5432/divap",
    )

    repo = TradeRepository(database_url)
    rows = repo.list_otc_closed_legs(limit=args.limit)
    legs = [leg for row in rows if (leg := leg_from_row(row)) is not None]
    cycles = group_otc_cycles(legs)

    if not cycles:
        print("Nenhum ciclo OTC fechado encontrado.", file=sys.stderr)
        return 1

    payoff_default = (args.payoff / Decimal("100")).quantize(Decimal("0.0001"))
    strategies = [
        SimulationStrategy.REAL,
        SimulationStrategy.MULTIPLIER,
        SimulationStrategy.RECOVERY,
        SimulationStrategy.NO_GALE,
    ]
    summaries = [
        summarize_strategy(
            cycles,
            strategy,
            payoff_default=payoff_default,
            multiplier=args.multiplier,
            recovery_target_usd=args.recovery_target,
        )
        for strategy in strategies
    ]
    outcomes = count_outcomes(cycles)
    report = format_simulation_report(
        cycles,
        summaries,
        outcomes,
        payoff_pct=args.payoff,
        multiplier=args.multiplier,
        recovery_target_usd=args.recovery_target,
        leg_count=len(legs),
    )

    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Relatório salvo em {args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
