from src.execution.gate import should_execute_trade
from src.execution.risk_manager import calculate_quote_amount, risk_reward_ratio

__all__ = [
    "TradeExecutor",
    "TradeExecutionResult",
    "calculate_quote_amount",
    "risk_reward_ratio",
    "should_execute_trade",
]


def __getattr__(name: str):
    if name == "TradeExecutor":
        from src.execution.trade_executor import TradeExecutor

        return TradeExecutor
    if name == "TradeExecutionResult":
        from src.execution.trade_executor import TradeExecutionResult

        return TradeExecutionResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
