from celery import Celery

from src.core.config import settings

celery_app = Celery(
    "divap_trader",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.alerts.scheduler", "src.execution.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "scan-divap-setups": {
            "task": "src.alerts.scheduler.scan_all_symbols",
            "schedule": 300.0,  # 5 min tick — profile throttles actual scan
        },
        "monitor-open-trades": {
            "task": "src.execution.tasks.monitor_open_trades",
            "schedule": 300.0,  # 5 min
        },
        "beat-heartbeat": {
            "task": "src.execution.tasks.beat_heartbeat",
            "schedule": 60.0,
        },
    },
)
