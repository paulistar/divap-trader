"""Tests for OTC Telegram auto-listener."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from src.otc.models import OtcSignal
from src.otc.telegram_handler import process_incoming_message
from src.otc.telegram_listener import extract_message
from src.otc.telegram_utils import chat_id_matches


SIGNAL_TEXT = """
✅ ENTRADA CONFIRMADA ✅
Ativo: FORDOTC
Expiração: M1
COMPRA
Entrada: 16:32
Fazer até 2 proteções
1º PROTEÇÃO: TERMINA EM: 16:33h
2º PROTEÇÃO: TERMINA EM: 16:34h
"""


def test_extract_message_from_group() -> None:
    update = {
        "update_id": 1,
        "message": {
            "message_id": 99,
            "chat": {"id": -1001234567890, "type": "supergroup"},
            "text": SIGNAL_TEXT,
        },
    }
    extracted = extract_message(update)
    assert extracted == ("-1001234567890", SIGNAL_TEXT, 99)


def test_chat_id_matches_numeric() -> None:
    assert chat_id_matches("-1001234567890", "-1001234567890")
    assert chat_id_matches("-1001234567890", "1234567890")
    assert not chat_id_matches("-1001234567890", "-100999")


@patch("src.otc.telegram_handler.is_duplicate_message", return_value=False)
@patch("src.otc.telegram_handler.dispatch_otc_signal")
def test_process_telegram_text_queues_signal(
    mock_dispatch: MagicMock,
    _mock_dedup: MagicMock,
) -> None:
    mock_dispatch.return_value = {"queued": True, "task_id": "abc"}
    outcome = process_incoming_message(
        "-1001234567890",
        SIGNAL_TEXT,
        99,
        source_chat_id="-1001234567890",
    )
    assert outcome is not None
    assert outcome["queued"] is True
    mock_dispatch.assert_called_once()
    signal = mock_dispatch.call_args[0][0]
    assert isinstance(signal, OtcSignal)
    assert signal.asset == "FORDOTC"


@patch("src.otc.telegram_handler.is_duplicate_message", return_value=True)
@patch("src.otc.telegram_handler.dispatch_otc_signal")
def test_process_telegram_text_skips_duplicate(
    mock_dispatch: MagicMock,
    _mock_dedup: MagicMock,
) -> None:
    outcome = process_incoming_message(
        "-1001234567890",
        SIGNAL_TEXT,
        99,
        source_chat_id="-1001234567890",
    )
    assert outcome is None
    mock_dispatch.assert_not_called()


def test_process_telegram_text_ignores_other_chats() -> None:
    outcome = process_incoming_message(
        "-100999",
        SIGNAL_TEXT,
        1,
        source_chat_id="-1001234567890",
        dedup=False,
    )
    assert outcome is None
