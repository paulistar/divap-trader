"""Simulação retroativa de ciclos OTC (real vs gale multiplier vs recovery vs sem gale)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_UP, Decimal
from enum import Enum

from src.otc.martingale import stake_for_level
from src.otc.models import OtcMartingale

DEFAULT_PAYOFF = Decimal("0.87")
DEFAULT_MULTIPLIER = Decimal("2.2")
MAX_PROTECTIONS = 2


class CycleOutcome(str, Enum):
    WIN_L0 = "win_l0"
    WIN_P1 = "win_p1"
    WIN_P2 = "win_p2"
    LOSS_FULL = "loss_full"
    INCOMPLETE = "incomplete"


class SimulationStrategy(str, Enum):
    REAL = "real"
    MULTIPLIER = "multiplier"
    RECOVERY = "recovery"
    NO_GALE = "no_gale"


@dataclass(frozen=True, slots=True)
class OtcLeg:
    id: int
    symbol: str
    direction: str
    stake_usd: Decimal
    pnl_usd: Decimal
    close_reason: str
    closed_at: datetime


@dataclass(frozen=True, slots=True)
class OtcCycle:
    legs: tuple[OtcLeg, ...]

    @property
    def base_stake(self) -> Decimal:
        return self.legs[0].stake_usd

    @property
    def real_pnl(self) -> Decimal:
        return sum((leg.pnl_usd for leg in self.legs), Decimal("0"))

    @property
    def max_legs(self) -> int:
        return len(self.legs) - 1


def leg_from_row(row: dict) -> OtcLeg | None:
    closed_at = row.get("closed_at")
    if closed_at is None:
        return None
    stake = Decimal(str(row.get("quantity") or 0))
    pnl = Decimal(str(row.get("pnl_usdt") or 0))
    if stake <= 0:
        return None
    return OtcLeg(
        id=int(row["id"]),
        symbol=str(row.get("symbol") or ""),
        direction=str(row.get("direction") or ""),
        stake_usd=stake,
        pnl_usd=pnl,
        close_reason=str(row.get("close_reason") or ""),
        closed_at=closed_at,
    )


def group_otc_cycles(legs: list[OtcLeg]) -> list[OtcCycle]:
    """Agrupa pernas em ciclos martingale usando close_reason e ordem temporal."""
    ordered = sorted(legs, key=lambda leg: leg.closed_at)
    cycles: list[tuple[OtcLeg, ...]] = []
    current: list[OtcLeg] = []

    for leg in ordered:
        if leg.close_reason == "expiry":
            if current:
                cycles.append(tuple(current))
            current = [leg]
        elif current:
            current.append(leg)
        else:
            continue

        if leg.close_reason == "expiry" and leg.pnl_usd > 0:
            cycles.append(tuple(current))
            current = []
        elif leg.close_reason == "expiry_p1" and leg.pnl_usd > 0:
            cycles.append(tuple(current))
            current = []
        elif leg.close_reason == "expiry_p2":
            cycles.append(tuple(current))
            current = []

    if current:
        cycles.append(tuple(current))
    return [OtcCycle(legs=c) for c in cycles]


def classify_cycle_outcome(cycle: OtcCycle) -> CycleOutcome:
    if not cycle.legs:
        return CycleOutcome.INCOMPLETE

    last = cycle.legs[-1]
    if len(cycle.legs) == 1:
        return CycleOutcome.WIN_L0 if last.pnl_usd > 0 else CycleOutcome.INCOMPLETE

    if last.close_reason == "expiry_p2":
        return CycleOutcome.WIN_P2 if last.pnl_usd > 0 else CycleOutcome.LOSS_FULL
    if last.close_reason == "expiry_p1" and last.pnl_usd > 0:
        return CycleOutcome.WIN_P1
    if last.close_reason == "expiry" and last.pnl_usd > 0:
        return CycleOutcome.WIN_L0
    return CycleOutcome.INCOMPLETE


def observed_payoff(cycle: OtcCycle, default: Decimal = DEFAULT_PAYOFF) -> Decimal:
    for leg in cycle.legs:
        if leg.pnl_usd > 0 and leg.stake_usd > 0:
            return (leg.pnl_usd / leg.stake_usd).quantize(Decimal("0.0001"))
    return default


def build_multiplier_ladder(
    base_stake: Decimal,
    *,
    max_protections: int = MAX_PROTECTIONS,
    multiplier: Decimal = DEFAULT_MULTIPLIER,
) -> tuple[Decimal, ...]:
    mg = OtcMartingale(
        enabled=True,
        max_protections=max_protections,
        multiplier=multiplier,
    )
    return tuple(
        stake_for_level(base_stake, mg, level)
        for level in range(max_protections + 1)
    )


def build_recovery_ladder(
    base_stake: Decimal,
    *,
    max_protections: int = MAX_PROTECTIONS,
    payoff: Decimal = DEFAULT_PAYOFF,
    recovery_target_usd: Decimal = Decimal("0"),
) -> tuple[Decimal, ...]:
    if payoff <= 0:
        raise ValueError("payoff must be positive")

    stakes: list[Decimal] = [base_stake.quantize(Decimal("0.01"))]
    accumulated = Decimal("0")
    for _ in range(max_protections):
        accumulated += stakes[-1]
        next_stake = (accumulated + recovery_target_usd) / payoff
        stakes.append(next_stake.quantize(Decimal("0.01"), rounding=ROUND_UP))
    return tuple(stakes)


def _win_pnl(stake: Decimal, payoff: Decimal) -> Decimal:
    return (stake * payoff).quantize(Decimal("0.01"))


def simulate_cycle_pnl(
    cycle: OtcCycle,
    strategy: SimulationStrategy,
    *,
    outcome: CycleOutcome | None = None,
    payoff: Decimal | None = None,
    multiplier: Decimal = DEFAULT_MULTIPLIER,
    recovery_target_usd: Decimal = Decimal("0"),
) -> Decimal:
    if strategy == SimulationStrategy.REAL:
        return cycle.real_pnl

    resolved_outcome = outcome or classify_cycle_outcome(cycle)
    resolved_payoff = payoff if payoff is not None else observed_payoff(cycle)
    base = cycle.base_stake

    if strategy == SimulationStrategy.NO_GALE:
        if resolved_outcome == CycleOutcome.WIN_L0:
            return _win_pnl(base, resolved_payoff)
        return -base

    if strategy == SimulationStrategy.MULTIPLIER:
        ladder = build_multiplier_ladder(
            base,
            max_protections=MAX_PROTECTIONS,
            multiplier=multiplier,
        )
    else:
        ladder = build_recovery_ladder(
            base,
            max_protections=MAX_PROTECTIONS,
            payoff=resolved_payoff,
            recovery_target_usd=recovery_target_usd,
        )

    return _simulate_from_ladder(resolved_outcome, ladder, resolved_payoff)


def _simulate_from_ladder(
    outcome: CycleOutcome,
    ladder: tuple[Decimal, ...],
    payoff: Decimal,
) -> Decimal:
    if outcome == CycleOutcome.WIN_L0:
        return _win_pnl(ladder[0], payoff)

    total = -ladder[0]
    if outcome == CycleOutcome.WIN_P1:
        return total + _win_pnl(ladder[1], payoff)

    if len(ladder) > 1:
        total -= ladder[1]
    if outcome == CycleOutcome.WIN_P2:
        return total + _win_pnl(ladder[2], payoff)

    if outcome == CycleOutcome.LOSS_FULL:
        return sum((-stake for stake in ladder), Decimal("0"))

    return -ladder[0]


@dataclass(frozen=True, slots=True)
class OutcomeCounts:
    win_l0: int = 0
    win_p1: int = 0
    win_p2: int = 0
    loss_full: int = 0
    incomplete: int = 0

    @property
    def total(self) -> int:
        return self.win_l0 + self.win_p1 + self.win_p2 + self.loss_full + self.incomplete


@dataclass(frozen=True, slots=True)
class StrategySummary:
    strategy: SimulationStrategy
    total_pnl: Decimal
    cycle_count: int
    avg_pnl_per_cycle: Decimal
    max_cycle_loss: Decimal
    max_cycle_risk: Decimal

    @property
    def label(self) -> str:
        labels = {
            SimulationStrategy.REAL: "Real (histórico)",
            SimulationStrategy.MULTIPLIER: "Gale multiplier (atual)",
            SimulationStrategy.RECOVERY: "Gale recovery (payoff)",
            SimulationStrategy.NO_GALE: "Sem gale (só entrada)",
        }
        return labels[self.strategy]


def summarize_strategy(
    cycles: list[OtcCycle],
    strategy: SimulationStrategy,
    *,
    payoff_default: Decimal = DEFAULT_PAYOFF,
    multiplier: Decimal = DEFAULT_MULTIPLIER,
    recovery_target_usd: Decimal = Decimal("0"),
) -> StrategySummary:
    pnls: list[Decimal] = []
    max_risk = Decimal("0")

    for cycle in cycles:
        outcome = classify_cycle_outcome(cycle)
        payoff = observed_payoff(cycle, payoff_default)
        pnl = simulate_cycle_pnl(
            cycle,
            strategy,
            outcome=outcome,
            payoff=payoff,
            multiplier=multiplier,
            recovery_target_usd=recovery_target_usd,
        )
        pnls.append(pnl)

        if strategy == SimulationStrategy.MULTIPLIER:
            ladder = build_multiplier_ladder(cycle.base_stake, multiplier=multiplier)
        elif strategy == SimulationStrategy.RECOVERY:
            ladder = build_recovery_ladder(
                cycle.base_stake,
                payoff=payoff,
                recovery_target_usd=recovery_target_usd,
            )
        elif strategy == SimulationStrategy.NO_GALE:
            ladder = (cycle.base_stake,)
        else:
            ladder = tuple(leg.stake_usd for leg in cycle.legs)

        max_risk = max(max_risk, sum(ladder, Decimal("0")))

    total = sum(pnls, Decimal("0"))
    count = len(pnls)
    avg = (total / count).quantize(Decimal("0.01")) if count else Decimal("0")
    max_loss = min(pnls) if pnls else Decimal("0")

    return StrategySummary(
        strategy=strategy,
        total_pnl=total.quantize(Decimal("0.01")),
        cycle_count=count,
        avg_pnl_per_cycle=avg,
        max_cycle_loss=max_loss,
        max_cycle_risk=max_risk.quantize(Decimal("0.01")),
    )


def count_outcomes(cycles: list[OtcCycle]) -> OutcomeCounts:
    tallies = {o: 0 for o in CycleOutcome}
    for cycle in cycles:
        tallies[classify_cycle_outcome(cycle)] += 1
    return OutcomeCounts(
        win_l0=tallies[CycleOutcome.WIN_L0],
        win_p1=tallies[CycleOutcome.WIN_P1],
        win_p2=tallies[CycleOutcome.WIN_P2],
        loss_full=tallies[CycleOutcome.LOSS_FULL],
        incomplete=tallies[CycleOutcome.INCOMPLETE],
    )


def format_simulation_report(
    cycles: list[OtcCycle],
    summaries: list[StrategySummary],
    outcomes: OutcomeCounts,
    *,
    payoff_pct: Decimal,
    multiplier: Decimal,
    recovery_target_usd: Decimal,
    leg_count: int,
) -> str:
    lines = [
        "# Simulação retroativa OTC (IQ Option)",
        "",
        f"- Pernas analisadas: **{leg_count}**",
        f"- Ciclos agrupados: **{len(cycles)}**",
        f"- Payoff default: **{payoff_pct}%** (por ciclo usa payout observado quando houve win)",
        f"- Multiplier (cenário atual): **{multiplier}**",
        f"- Recovery target: **US$ {recovery_target_usd}**",
        "",
        "## Distribuição de desfechos (histórico real)",
        "",
        f"| Desfecho | Qtd | % |",
        f"|----------|-----|---|",
    ]

    total = outcomes.total or 1
    for label, count in [
        ("Win na entrada", outcomes.win_l0),
        ("Win na 1ª proteção", outcomes.win_p1),
        ("Win na 2ª proteção", outcomes.win_p2),
        ("Loss total (3 pernas)", outcomes.loss_full),
        ("Incompleto / sem gale", outcomes.incomplete),
    ]:
        pct = round(count / total * 100, 1)
        lines.append(f"| {label} | {count} | {pct}% |")

    lines.extend(["", "## PnL total por estratégia", "", "| Estratégia | PnL total | Média/ciclo | Pior ciclo | Risco máx/ciclo |", "|------------|-----------|-------------|------------|-----------------|"])

    for summary in summaries:
        lines.append(
            f"| {summary.label} | US$ {summary.total_pnl:+.2f} | US$ {summary.avg_pnl_per_cycle:+.2f} | "
            f"US$ {summary.max_cycle_loss:+.2f} | US$ {summary.max_cycle_risk:.2f} |"
        )

    real = next((s for s in summaries if s.strategy == SimulationStrategy.REAL), None)
    recovery = next((s for s in summaries if s.strategy == SimulationStrategy.RECOVERY), None)
    mult = next((s for s in summaries if s.strategy == SimulationStrategy.MULTIPLIER), None)
    no_gale = next((s for s in summaries if s.strategy == SimulationStrategy.NO_GALE), None)

    lines.extend(["", "## Deltas vs real", ""])
    if real and recovery:
        delta = recovery.total_pnl - real.total_pnl
        lines.append(f"- **Recovery vs Real:** US$ {delta:+.2f}")
    if real and mult:
        delta = mult.total_pnl - real.total_pnl
        lines.append(f"- **Multiplier vs Real:** US$ {delta:+.2f}")
    if real and no_gale:
        delta = no_gale.total_pnl - real.total_pnl
        lines.append(f"- **Sem gale vs Real:** US$ {delta:+.2f}")

    if recovery and mult:
        lines.extend(
            [
                "",
                "## Leitura",
                "",
                f"- Recovery economizaria **US$ {(mult.max_cycle_risk - recovery.max_cycle_risk):.2f}** "
                f"no pior ciclo teórico (risco máx/ciclo {mult.max_cycle_risk:.2f} → {recovery.max_cycle_risk:.2f}).",
            ]
        )

    lines.append("")
    lines.append(
        "> Mesmos desfechos do histórico; apenas o **tamanho das apostas** muda entre cenários."
    )
    return "\n".join(lines)
