from unittest.mock import MagicMock, patch

from src.alerts.telegram import TelegramNotifier


@patch("src.alerts.telegram.httpx.post")
def test_telegram_send_success(mock_post: MagicMock) -> None:
    mock_post.return_value.raise_for_status = MagicMock()
    notifier = TelegramNotifier(bot_token="token", chat_id="123")
    assert notifier.send("test message") is True
    mock_post.assert_called_once()


def test_telegram_not_configured() -> None:
    notifier = TelegramNotifier(bot_token="", chat_id="")
    assert notifier.send("test") is False
