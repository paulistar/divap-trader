from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    api_key: str = Field(default="change-me", alias="API_KEY")
    dashboard_token: str = Field(default="", alias="DASHBOARD_TOKEN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(
        default="postgresql://divap:divap@localhost:5432/divap",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    binance_api_key: str = Field(default="", alias="BINANCE_API_KEY")
    binance_api_secret: str = Field(default="", alias="BINANCE_API_SECRET")
    binance_use_testnet: bool = Field(default=True, alias="BINANCE_USE_TESTNET")

    context_enabled: bool = Field(default=True, alias="CONTEXT_ENABLED")
    context_news_limit: int = Field(default=5, alias="CONTEXT_NEWS_LIMIT")
    cryptopanic_api_key: str = Field(default="", alias="CRYPTOPANIC_API_KEY")

    trading_enabled: bool = Field(default=False, alias="TRADING_ENABLED")
    trading_mode: str = Field(default="testnet", alias="TRADING_MODE")
    trading_min_confidence: str = Field(default="high", alias="TRADING_MIN_CONFIDENCE")
    trading_block_on_context_reject: bool = Field(
        default=True, alias="TRADING_BLOCK_ON_CONTEXT_REJECT"
    )
    trading_max_open_trades: int = Field(default=5, alias="TRADING_MAX_OPEN_TRADES")
    trading_dry_run: bool = Field(default=False, alias="TRADING_DRY_RUN")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    openai_model_triage: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL_TRIAGE")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    vapid_public_key: str = Field(default="", alias="VAPID_PUBLIC_KEY")
    vapid_private_key: str = Field(default="", alias="VAPID_PRIVATE_KEY")
    vapid_claims_sub: str = Field(
        default="mailto:trade@martstudiosbr.com.br",
        alias="VAPID_CLAIMS_SUB",
    )

    fxcm_access_token: str = Field(default="", alias="FXCM_ACCESS_TOKEN")
    fxcm_server: str = Field(default="demo", alias="FXCM_SERVER")
    fxcm_account_id: str = Field(default="", alias="FXCM_ACCOUNT_ID")

    iqoption_email: str = Field(default="", alias="IQOPTION_EMAIL")
    iqoption_password: str = Field(default="", alias="IQOPTION_PASSWORD")
    iqoption_account_mode: str = Field(default="PRACTICE", alias="IQOPTION_ACCOUNT_MODE")
    iqoption_mcp_token: str = Field(default="", alias="IQOPTION_MCP_TOKEN")
    iqoption_mcp_url: str = Field(
        default="https://digital-options.mcp.iqoption.com",
        alias="IQOPTION_MCP_URL",
    )
    otc_trading_enabled: bool = Field(default=False, alias="OTC_TRADING_ENABLED")
    otc_telegram_chat_id: str = Field(default="", alias="OTC_TELEGRAM_CHAT_ID")
    telegram_api_id: int = Field(default=0, alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(default="", alias="TELEGRAM_API_HASH")
    telegram_user_session: str = Field(default="", alias="TELEGRAM_USER_SESSION")

    tasso_telegram_enabled: bool = Field(default=False, alias="TASSO_TELEGRAM_ENABLED")
    tasso_financial_move_bot: str = Field(
        default="FinancialMoveBot",
        alias="TASSO_FINANCIAL_MOVE_BOT",
        description="Username do Financial Move Bot 3.0 (ex: FinancialMoveBot ou @FinancialMoveBot)",
    )

    @field_validator("vapid_private_key", mode="before")
    @classmethod
    def normalize_vapid_private_key(cls, value: object) -> object:
        if isinstance(value, str) and "\\n" in value:
            return value.replace("\\n", "\n")
        return value

    @field_validator(
        "api_key",
        "dashboard_token",
        "binance_api_key",
        "binance_api_secret",
        "fxcm_access_token",
        "iqoption_email",
        "iqoption_password",
        "iqoption_mcp_token",
        "iqoption_mcp_url",
        "telegram_api_hash",
        "telegram_user_session",
        "tasso_financial_move_bot",
        mode="before",
    )
    @classmethod
    def strip_whitespace(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
