"""Accumulates per-scan statistics for the dashboard."""

from __future__ import annotations

from collections import defaultdict


class ScanMetrics:
    def __init__(self) -> None:
        self.pairs_scanned = 0
        self.setups_detected = 0
        self.duplicates_skipped = 0
        self.signals_saved = 0
        self.trades_executed = 0
        self.gate_blocks: dict[str, int] = defaultdict(int)

    def record_gate_block(self, reason: str) -> None:
        self.gate_blocks[reason] += 1

    def to_dict(self) -> dict:
        return {
            "pairs_scanned": self.pairs_scanned,
            "setups_detected": self.setups_detected,
            "duplicates_skipped": self.duplicates_skipped,
            "signals_saved": self.signals_saved,
            "trades_executed": self.trades_executed,
            "gate_blocks": dict(self.gate_blocks),
        }
