from __future__ import annotations

from src.core.celery_app import celery_app
from src.otc.executor import OtcExecutor
from src.otc.models import OtcSequenceResult, OtcSignal
from src.otc.schedule import deserialize_signal, serialize_signal


def sequence_result_to_dict(result: OtcSequenceResult) -> dict:
    last_leg = result.legs[-1] if result.legs else None
    return {
        "executed": result.executed,
        "reason": result.reason,
        "asset": result.asset,
        "direction": result.direction,
        "total_pnl_usd": (
            str(result.total_pnl_usd) if result.total_pnl_usd is not None else None
        ),
        "dry_run": result.dry_run,
        "legs": [
            {
                "protection_level": leg.protection_level,
                "executed": leg.executed,
                "reason": leg.reason,
                "trade_id": leg.trade_id,
                "order_id": leg.order_id,
                "asset": leg.asset,
                "stake_usd": str(leg.stake_usd),
                "pnl_usd": str(leg.pnl_usd) if leg.pnl_usd is not None else None,
                "dry_run": leg.dry_run,
            }
            for leg in result.legs
        ],
        "trade_id": last_leg.trade_id if last_leg else None,
        "order_id": last_leg.order_id if last_leg else None,
        "stake_usd": str(last_leg.stake_usd) if last_leg else None,
        "pnl_usd": (
            str(last_leg.pnl_usd)
            if last_leg and last_leg.pnl_usd is not None
            else None
        ),
    }


def should_queue_otc_execution(signal: OtcSignal) -> bool:
    return signal.entry_time is not None or bool(signal.protection_schedule)


@celery_app.task(name="src.otc.tasks.execute_otc_signal")
def execute_otc_signal(signal_payload: dict) -> dict:
    signal = deserialize_signal(signal_payload)
    result = OtcExecutor().try_execute(signal)
    return sequence_result_to_dict(result)
