"""Web Push notifications for high-confidence DIVAP signals."""

from __future__ import annotations

import json
import logging

from src.api.push_subscriptions import list_subscriptions, remove_subscription, save_subscription
from src.core.config import settings

logger = logging.getLogger(__name__)


def vapid_public_key() -> str | None:
    key = settings.vapid_public_key.strip()
    return key or None


def vapid_configured() -> bool:
    return bool(settings.vapid_public_key.strip() and settings.vapid_private_key.strip())


def store_subscription(subscription: dict) -> None:
    endpoint = subscription.get("endpoint")
    if not endpoint:
        return
    save_subscription(endpoint, subscription)


def notify_subscription_test(subscription: dict) -> bool:
    """Send a welcome test push to a single subscription. Returns True if sent."""
    if not vapid_configured():
        return False

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed — push disabled")
        return False

    endpoint = subscription.get("endpoint", "")
    if not endpoint:
        return False

    payload = json.dumps(
        {
            "title": "DIVAP — push ativado",
            "body": "Se você viu isto, alertas de alta confiança chegam mesmo com o app fechado.",
            "url": "/dashboard",
            "alert_id": 0,
        }
    )
    try:
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_claims_sub},
        )
        return True
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None) if exc.response else None
        if status in (404, 410):
            remove_subscription(endpoint)
        logger.warning("Welcome push failed %s: %s", endpoint[:48], exc)
    except Exception as exc:
        logger.warning("Welcome push error: %s", exc)
    return False


def delete_subscription(endpoint: str) -> None:
    if endpoint:
        remove_subscription(endpoint)


def notify_test_push() -> int:
    """Send a test push to all subscribers. Returns count sent."""
    if not vapid_configured():
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed — push disabled")
        return 0

    payload = json.dumps(
        {
            "title": "DIVAP — teste de push",
            "body": "Se você viu isto, alertas de alta confiança estão ativos no celular.",
            "url": "/dashboard",
            "alert_id": 0,
        }
    )
    sent = 0
    for sub in list_subscriptions():
        endpoint = sub.get("endpoint", "")
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_claims_sub},
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None) if exc.response else None
            if status in (404, 410):
                remove_subscription(endpoint)
            logger.warning("Test push failed %s: %s", endpoint[:48], exc)
        except Exception as exc:
            logger.warning("Test push error: %s", exc)
    return sent


def notify_trade_opened(
    *,
    symbol: str,
    timeframe: str,
    direction: str,
    trade_id: int | None,
) -> int:
    """Web push quando um trade é aberto. Returns count sent."""
    if not vapid_configured():
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed — push disabled")
        return 0

    side = "Compra" if direction == "buy" else "Venda"
    trade_ref = f" #{trade_id}" if trade_id else ""
    payload = json.dumps(
        {
            "title": "DIVAP — trade aberto",
            "body": f"{symbol} {timeframe} · {side}{trade_ref}",
            "url": "/dashboard",
        }
    )
    sent = 0
    for sub in list_subscriptions():
        endpoint = sub.get("endpoint", "")
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_claims_sub},
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None) if exc.response else None
            if status in (404, 410):
                remove_subscription(endpoint)
            logger.warning("Push failed %s: %s", endpoint[:48], exc)
        except Exception as exc:
            logger.warning("Push error: %s", exc)
    return sent


def notify_high_confidence_signal(
    *,
    symbol: str,
    timeframe: str,
    direction: str,
    alert_id: int,
) -> int:
    """Send push to all subscribers. Returns count sent."""
    if not vapid_configured():
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed — push disabled")
        return 0

    side = "Compra" if direction == "buy" else "Venda"
    payload = json.dumps(
        {
            "title": "DIVAP — sinal alta confiança",
            "body": f"{symbol} {timeframe} · {side}",
            "url": "/dashboard",
            "alert_id": alert_id,
        }
    )
    sent = 0
    for sub in list_subscriptions():
        endpoint = sub.get("endpoint", "")
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_claims_sub},
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None) if exc.response else None
            if status in (404, 410):
                remove_subscription(endpoint)
            logger.warning("Push failed %s: %s", endpoint[:48], exc)
        except Exception as exc:
            logger.warning("Push error: %s", exc)
    return sent
