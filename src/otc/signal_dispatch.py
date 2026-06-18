from __future__ import annotations

from dataclasses import replace

from src.otc.config import load_otc_config, resolve_iq_asset
from src.otc.models import OtcSignal
from src.otc.schedule import leg_window_missed, resolve_leg_datetime, serialize_signal
from src.otc.tasks import execute_otc_signal, should_queue_otc_execution


def normalize_signal(signal: OtcSignal) -> OtcSignal:
    """Aplica aliases de ativo definidos no perfil OTC."""
    cfg = load_otc_config()
    resolved = resolve_iq_asset(signal.asset, cfg)
    if resolved == signal.asset:
        return signal
    return replace(signal, asset=resolved)


def build_schedule_preview(signal: OtcSignal) -> dict[str, str]:
    cfg = load_otc_config()
    max_prot = signal.max_auto_protections or cfg.martingale.max_protections
    schedule: dict[str, str] = {}
    for level in range(0, max_prot + 1):
        target = resolve_leg_datetime(signal, level, cfg.signal_timezone)
        if target is not None:
            schedule[f"leg_{level}"] = target.strftime("%Y-%m-%d %H:%M:%S %Z")
    return schedule


def dispatch_otc_signal(signal: OtcSignal) -> dict:
    """
    Enfileira sinal OTC no Celery (com horário) ou executa imediato.
    Retorna dict com queued/task_id ou erro de timing.
    """
    cfg = load_otc_config()
    prepared = normalize_signal(signal)

    missed, reason = leg_window_missed(
        prepared,
        0,
        cfg.signal_timezone,
        max_lateness_seconds=cfg.entry_max_lateness_seconds,
    )
    if missed:
        return {
            "queued": False,
            "skipped": True,
            "reason": reason,
            "asset": prepared.asset,
            "direction": prepared.direction,
        }

    if should_queue_otc_execution(prepared):
        task = execute_otc_signal.delay(serialize_signal(prepared))
        return {
            "queued": True,
            "task_id": task.id,
            "asset": prepared.asset,
            "direction": prepared.direction,
            "schedule": build_schedule_preview(prepared),
            "timezone": cfg.signal_timezone,
        }

    from src.otc.executor import OtcExecutor
    from src.otc.tasks import sequence_result_to_dict

    result = OtcExecutor().try_execute(prepared)
    return {
        "queued": False,
        "result": sequence_result_to_dict(result),
        "asset": prepared.asset,
        "direction": prepared.direction,
    }
