import logging

from src.core.beat_state import record_beat_heartbeat
from src.core.celery_app import celery_app
from src.execution.position_monitor import PositionMonitor

logger = logging.getLogger(__name__)


@celery_app.task(name="src.execution.tasks.beat_heartbeat")
def beat_heartbeat() -> dict[str, str]:
    record_beat_heartbeat()
    return {"status": "ok"}


@celery_app.task(name="src.execution.tasks.monitor_open_trades")
def monitor_open_trades() -> dict[str, int]:
    record_beat_heartbeat()
    logger.info("Monitoring open trades")
    return PositionMonitor().sync_open_positions()
