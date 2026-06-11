import logging

import httpx

from src.core.config import settings
from src.core.exceptions import DivapError

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        self._token = bot_token or settings.telegram_bot_token
        self._chat_id = chat_id or settings.telegram_chat_id

    def is_configured(self) -> bool:
        return bool(self._token and self._chat_id)

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        if not self.is_configured():
            logger.warning("Telegram not configured — skipping notification")
            return False

        url = TELEGRAM_API.format(token=self._token)
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            response = httpx.post(url, json=payload, timeout=15.0)
            response.raise_for_status()
            logger.info("Telegram alert sent")
            return True
        except httpx.HTTPError as exc:
            raise DivapError(f"Telegram send failed: {exc}") from exc
