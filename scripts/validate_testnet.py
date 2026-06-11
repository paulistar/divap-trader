#!/usr/bin/env python3
"""Valida prontidão do pipeline testnet (CLI)."""

from __future__ import annotations

import json
import sys

from src.trading.readiness import build_trading_readiness


def main() -> int:
    report = build_trading_readiness()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("ready") else 1


if __name__ == "__main__":
    sys.exit(main())
