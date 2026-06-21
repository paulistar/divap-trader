"""Tests for OTC ladder back-simulation."""

from datetime import datetime, timezone
from decimal import Decimal

from src.otc.simulation import (
    CycleOutcome,
    OtcCycle,
    OtcLeg,
    SimulationStrategy,
    build_multiplier_ladder,
    build_recovery_ladder,
    classify_cycle_outcome,
    count_outcomes,
    group_otc_cycles,
    simulate_cycle_pnl,
    summarize_strategy,
)


def _leg(
    leg_id: int,
    stake: str,
    pnl: str,
    close_reason: str,
    *,
    minute: int = 0,
) -> OtcLeg:
    return OtcLeg(
        id=leg_id,
        symbol="EUR/JPY (OTC)",
        direction="buy",
        stake_usd=Decimal(stake),
        pnl_usd=Decimal(pnl),
        close_reason=close_reason,
        closed_at=datetime(2026, 6, 20, 15, minute, tzinfo=timezone.utc),
    )


def test_build_multiplier_ladder_matches_martingale() -> None:
    ladder = build_multiplier_ladder(Decimal("5"))
    assert ladder == (Decimal("5"), Decimal("11.00"), Decimal("24.20"))


def test_build_recovery_ladder_payoff_87() -> None:
    ladder = build_recovery_ladder(Decimal("5"), payoff=Decimal("0.87"))
    assert ladder[0] == Decimal("5.00")
    assert ladder[1] == Decimal("5.75")
    assert ladder[2] == Decimal("12.36")


def test_group_cycles_win_l0() -> None:
    legs = [_leg(1, "5", "4.35", "expiry")]
    cycles = group_otc_cycles(legs)
    assert len(cycles) == 1
    assert len(cycles[0].legs) == 1
    assert classify_cycle_outcome(cycles[0]) == CycleOutcome.WIN_L0


def test_group_cycles_win_p1() -> None:
    legs = [
        _leg(1, "5", "-5", "expiry", minute=0),
        _leg(2, "11", "9.57", "expiry_p1", minute=1),
    ]
    cycles = group_otc_cycles(legs)
    assert len(cycles) == 1
    assert classify_cycle_outcome(cycles[0]) == CycleOutcome.WIN_P1


def test_group_cycles_loss_full() -> None:
    legs = [
        _leg(1, "5", "-5", "expiry", minute=0),
        _leg(2, "11", "-11", "expiry_p1", minute=1),
        _leg(3, "24.20", "-24.20", "expiry_p2", minute=2),
    ]
    cycles = group_otc_cycles(legs)
    assert classify_cycle_outcome(cycles[0]) == CycleOutcome.LOSS_FULL


def test_simulate_recovery_vs_multiplier_on_win_p1() -> None:
    cycle = OtcCycle(
        legs=(
            _leg(1, "5", "-5", "expiry", minute=0),
            _leg(2, "11", "9.57", "expiry_p1", minute=1),
        )
    )
    payoff = Decimal("0.87")
    mult_pnl = simulate_cycle_pnl(
        cycle,
        SimulationStrategy.MULTIPLIER,
        payoff=payoff,
    )
    rec_pnl = simulate_cycle_pnl(
        cycle,
        SimulationStrategy.RECOVERY,
        payoff=payoff,
    )
    assert mult_pnl == Decimal("-5") + Decimal("11") * payoff
    assert rec_pnl == Decimal("0.00")  # recovery 87%: -5 + 5.75×0.87 ≈ 0
    assert mult_pnl > rec_pnl


def test_simulate_no_gale_only_entry_loss_on_p1_win_path() -> None:
    cycle = OtcCycle(
        legs=(
            _leg(1, "5", "-5", "expiry", minute=0),
            _leg(2, "11", "9.57", "expiry_p1", minute=1),
        )
    )
    pnl = simulate_cycle_pnl(cycle, SimulationStrategy.NO_GALE, payoff=Decimal("0.87"))
    assert pnl == Decimal("-5")


def test_summarize_strategies_synthetic() -> None:
    cycles = [
        OtcCycle(legs=(_leg(1, "5", "4.35", "expiry"),)),
        OtcCycle(
            legs=(
                _leg(2, "5", "-5", "expiry", minute=10),
                _leg(3, "11", "9.57", "expiry_p1", minute=11),
            )
        ),
    ]
    real = summarize_strategy(cycles, SimulationStrategy.REAL)
    recovery = summarize_strategy(cycles, SimulationStrategy.RECOVERY)
    no_gale = summarize_strategy(cycles, SimulationStrategy.NO_GALE)

    assert real.total_pnl == Decimal("8.92")
    assert recovery.total_pnl == Decimal("4.35")
    assert no_gale.total_pnl == Decimal("-0.65")
    mult = summarize_strategy(cycles, SimulationStrategy.MULTIPLIER)
    assert recovery.max_cycle_risk < mult.max_cycle_risk


def test_count_outcomes() -> None:
    cycles = [
        OtcCycle(legs=(_leg(1, "5", "4.35", "expiry"),)),
        OtcCycle(
            legs=(
                _leg(2, "5", "-5", "expiry", minute=10),
                _leg(3, "11", "9.57", "expiry_p1", minute=11),
            )
        ),
        OtcCycle(
            legs=(
                _leg(4, "5", "-5", "expiry", minute=20),
                _leg(5, "11", "-11", "expiry_p1", minute=21),
                _leg(6, "24.20", "-24.20", "expiry_p2", minute=22),
            )
        ),
    ]
    counts = count_outcomes(cycles)
    assert counts.win_l0 == 1
    assert counts.win_p1 == 1
    assert counts.loss_full == 1
    assert counts.total == 3
