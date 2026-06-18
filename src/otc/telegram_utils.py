from __future__ import annotations


def chat_id_matches(configured: str, incoming: str) -> bool:
    configured = configured.strip()
    incoming = incoming.strip()
    if not configured:
        return False
    if configured.startswith("@"):
        return configured.lower() == incoming.lower()
    try:
        return int(configured) == int(incoming)
    except ValueError:
        return configured == incoming
