import logging

from src.core.beat_state import record_beat_heartbeat
from src.core.celery_app import celery_app
from src.core.monitor_state import record_monitor, should_run_monitor
from src.core.scan_plan import get_active_scan_plan
from src.execution.position_monitor import PositionMonitor

logger = logging.getLogger(__name__)


@celery_app.task(name="src.execution.tasks.beat_heartbeat")
def beat_heartbeat() -> dict[str, str]:
    record_beat_heartbeat()
    return {"status": "ok"}


@celery_app.task(name="src.execution.tasks.monitor_open_trades")
def monitor_open_trades() -> dict[str, int | bool | str]:
    record_beat_heartbeat()
    plan = get_active_scan_plan()
    if not should_run_monitor(plan.profile_id):
        logger.info(
            "Monitor skipped for %s — interval %ss not elapsed",
            plan.profile_id,
            plan.monitor_interval_seconds,
        )
        return {
            "skipped": True,
            "profile_id": plan.profile_id,
            "checked": 0,
            "closed": 0,
            "errors": 0,
        }

    logger.info(
        "Monitoring open trades (%s, every %ss)",
        plan.profile_name,
        plan.monitor_interval_seconds,
    )
    result = PositionMonitor().sync_open_positions()
    result["profile_id"] = plan.profile_id
    record_monitor(plan.profile_id, result)
    return result
