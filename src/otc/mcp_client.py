from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal
from functools import lru_cache
from typing import Any

import httpx

from src.core.config import settings
from src.core.exceptions import ExchangeError

logger = logging.getLogger(__name__)

DEFAULT_MCP_URL = "https://digital-options.mcp.iqoption.com"
PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "divap-trader"
CLIENT_VERSION = "1.0.0"


def mcp_configured() -> bool:
    return bool(settings.iqoption_mcp_token.strip())


def reset_mcp_client() -> None:
    get_mcp_client.cache_clear()


def _parse_tool_payload(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("isError"):
        message = "MCP tool error"
        content = result.get("content") or []
        if content and isinstance(content[0], dict):
            message = str(content[0].get("text") or message)
        raise ExchangeError(message)

    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured

    content = result.get("content") or []
    if content and isinstance(content[0], dict):
        text = content[0].get("text")
        if isinstance(text, str) and text.strip().startswith("{"):
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed

    raise ExchangeError("Resposta MCP sem structuredContent")


class IqOptionMcpClient:
    """Cliente HTTP MCP (Streamable HTTP) para digital-options."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token.strip()
        self._session_id: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _post(self, payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(self._base_url, headers=self._headers(), json=payload)
        if response.status_code == 401:
            raise ExchangeError("Token MCP IQ Option inválido ou ausente")
        response.raise_for_status()
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self._session_id = session_id
        if not response.content.strip():
            return {}
        data = response.json()
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "result" in item:
                    return item
            raise ExchangeError("Resposta MCP inválida (lista sem result)")
        return data

    def _ensure_session(self) -> None:
        if self._session_id:
            return
        init_id = str(uuid.uuid4())
        init_response = self._post(
            {
                "jsonrpc": "2.0",
                "id": init_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
                },
            }
        )
        if "error" in init_response:
            raise ExchangeError(f"MCP initialize falhou: {init_response['error']}")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ensure_session()
        request_id = str(uuid.uuid4())
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
        )
        if "error" in response:
            raise ExchangeError(f"MCP {name} falhou: {response['error']}")
        result = response.get("result")
        if not isinstance(result, dict):
            raise ExchangeError(f"MCP {name} retornou payload inválido")
        return _parse_tool_payload(result)


@lru_cache
def get_mcp_client() -> IqOptionMcpClient:
    token = settings.iqoption_mcp_token.strip()
    if not token:
        raise ExchangeError(
            "IQOPTION_MCP_TOKEN não configurado. "
            "Crie em IQ Option → Settings → AI integrations."
        )
    url = settings.iqoption_mcp_url.strip() or DEFAULT_MCP_URL
    return IqOptionMcpClient(base_url=url, token=token)


def mcp_call(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_mcp_client().call_tool(name, arguments)


def fetch_mcp_balance(account_mode: str) -> tuple[Decimal, int]:
    types = "TRAINING" if account_mode.upper() == "PRACTICE" else "NORMAL"
    payload = mcp_call("list_balances", {"types": types})
    balances = payload.get("balances") or []
    if not balances:
        raise ExchangeError(f"Nenhum saldo MCP encontrado (types={types})")

    if account_mode.upper() == "PRACTICE":
        training = [b for b in balances if b.get("type") == "training"]
        chosen = training[0] if training else balances[0]
    else:
        regular = [b for b in balances if b.get("type") == "regular"]
        chosen = regular[0] if regular else balances[0]

    amount = Decimal(str(chosen.get("amount", 0)))
    balance_id = int(chosen["balance_id"])
    return amount, balance_id


def fetch_mcp_capabilities() -> dict[str, Any]:
    return mcp_call("get_capabilities")
