from __future__ import annotations


def chat_id_matches(configured: str, incoming: str) -> bool:
    configured = configured.strip()
    incoming = incoming.strip()
    if not configured:
        return False
    if configured.startswith("@"):
        return configured.lower() == incoming.lower()
    try:
        configured_id = int(configured)
        incoming_id = int(incoming)
    except ValueError:
        return configured == incoming

    if configured_id == incoming_id:
        return True

    def channel_tail(value: int) -> int | None:
        text = str(value)
        if text.startswith("-100"):
            return int(text[4:])
        if value > 0:
            return value
        return None

    configured_tail = channel_tail(configured_id)
    incoming_tail = channel_tail(incoming_id)
    return (
        configured_tail is not None
        and incoming_tail is not None
        and configured_tail == incoming_tail
    )
