class DivapError(Exception):
    """Base exception for DIVAP trader."""


class ExchangeError(DivapError):
    """Exchange API or connectivity error."""


class DataNotFoundError(DivapError):
    """Requested market data not available."""


class ScannerError(DivapError):
    """DIVAP scanner processing error."""


class AnalysisError(DivapError):
    """LLM analysis error."""
