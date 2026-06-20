"""Gera bloco .env para colar no Easypanel a partir do runtime settings."""

from __future__ import annotations

from datetime import UTC, datetime

from src.core.config import Settings


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _secret_line(name: str, configured: bool) -> str:
    if configured:
        return f"# {name}=*** mantenha o valor já configurado no Easypanel ***"
    return f"{name}="


def build_env_export(cfg: Settings) -> str:
    """Bloco operacional + placeholders de segredos (valores sensíveis nunca exportados)."""
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# DIVAP Trader — bloco gerado pelo painel em {ts}",
        "# Cole/atualize no Easypanel → Environment. Não apague segredos já preenchidos.",
        "",
        "###############",
        "### Binance / DIVAP ###",
        "###############",
        f"TRADING_ENABLED={_bool_str(cfg.trading_enabled)}",
        f"TRADING_MODE={cfg.trading_mode}",
        f"BINANCE_USE_TESTNET={_bool_str(cfg.binance_use_testnet)}",
        f"TRADING_MIN_CONFIDENCE={cfg.trading_min_confidence}",
        f"TRADING_BLOCK_ON_CONTEXT_REJECT={_bool_str(cfg.trading_block_on_context_reject)}",
        f"TRADING_MAX_OPEN_TRADES={cfg.trading_max_open_trades}",
        f"TRADING_DRY_RUN={_bool_str(cfg.trading_dry_run)}",
        _secret_line("BINANCE_API_KEY", bool(cfg.binance_api_key)),
        _secret_line("BINANCE_API_SECRET", bool(cfg.binance_api_secret)),
        "",
        "###############",
        "### Contexto IA ###",
        "###############",
        f"CONTEXT_ENABLED={_bool_str(cfg.context_enabled)}",
        f"CONTEXT_NEWS_LIMIT={cfg.context_news_limit}",
        _secret_line("OPENAI_API_KEY", bool(cfg.openai_api_key)),
        f"OPENAI_MODEL={cfg.openai_model}",
        f"OPENAI_MODEL_TRIAGE={cfg.openai_model_triage}",
        _secret_line("CRYPTOPANIC_API_KEY", bool(cfg.cryptopanic_api_key)),
        "",
        "###############",
        "### Telegram (alertas DIVAP) ###",
        "###############",
        _secret_line("TELEGRAM_BOT_TOKEN", bool(cfg.telegram_bot_token)),
        f"TELEGRAM_CHAT_ID={cfg.telegram_chat_id or ''}",
        "",
        "###############",
        "### IQ Option / OTC ###",
        "###############",
        f"OTC_TRADING_ENABLED={_bool_str(cfg.otc_trading_enabled)}",
        f"IQOPTION_ACCOUNT_MODE={cfg.iqoption_account_mode}",
        f"IQOPTION_MCP_URL={cfg.iqoption_mcp_url}",
        _secret_line("IQOPTION_MCP_TOKEN", bool(cfg.iqoption_mcp_token)),
        _secret_line("IQOPTION_EMAIL", bool(cfg.iqoption_email)),
        _secret_line("IQOPTION_PASSWORD", bool(cfg.iqoption_password)),
        f"OTC_TELEGRAM_CHAT_ID={cfg.otc_telegram_chat_id or ''}",
        f"TELEGRAM_API_ID={cfg.telegram_api_id or 0}",
        _secret_line("TELEGRAM_API_HASH", bool(cfg.telegram_api_hash)),
        _secret_line("TELEGRAM_USER_SESSION", bool(cfg.telegram_user_session)),
        "",
        "###############",
        "### Tasso — Financial Move Bot ###",
        "###############",
        f"TASSO_TELEGRAM_ENABLED={_bool_str(cfg.tasso_telegram_enabled)}",
        f"TASSO_FINANCIAL_MOVE_BOT={cfg.tasso_financial_move_bot}",
        "",
        "###############",
        "### Invezt — Maia PREMIUM (briefing Binance) ###",
        "###############",
        f"INVEZT_TELEGRAM_ENABLED={_bool_str(cfg.invezt_telegram_enabled)}",
        f"INVEZT_TELEGRAM_CHAT_REF={cfg.invezt_telegram_chat_ref or ''}",
        "",
        "###############",
        "### Painel / push ###",
        "###############",
        _secret_line("DASHBOARD_TOKEN", bool(cfg.dashboard_token)),
        _secret_line("API_KEY", bool(cfg.api_key and cfg.api_key != "change-me")),
        _secret_line("VAPID_PUBLIC_KEY", bool(cfg.vapid_public_key)),
        _secret_line("VAPID_PRIVATE_KEY", bool(cfg.vapid_private_key)),
        f"VAPID_CLAIMS_SUB={cfg.vapid_claims_sub}",
        "",
    ]
    return "\n".join(lines)
