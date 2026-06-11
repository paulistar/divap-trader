import logging

from openai import OpenAI

from src.core.config import settings
from src.core.constants import MIN_CONFLUENCES_FOR_ALERT
from src.core.exceptions import AnalysisError
from src.context.models import MarketContext
from src.detection.divap_scanner import DIVAPSignal
from src.analysis.report_generator import build_user_message, load_system_prompt

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    def __init__(self, client: OpenAI | None = None) -> None:
        self._client = client

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not settings.openai_api_key:
                raise AnalysisError("OPENAI_API_KEY not configured")
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    def analyze(
        self,
        signal: DIVAPSignal,
        market_context: MarketContext | None = None,
    ) -> str:
        if signal.criteria.count < MIN_CONFLUENCES_FOR_ALERT:
            raise AnalysisError(
                f"LLM analysis requires >= {MIN_CONFLUENCES_FOR_ALERT} confluences"
            )

        try:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": load_system_prompt()},
                    {
                        "role": "user",
                        "content": build_user_message(signal, market_context),
                    },
                ],
                temperature=0.3,
            )
        except Exception as exc:
            raise AnalysisError(f"OpenAI request failed: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise AnalysisError("Empty response from OpenAI")

        logger.info("LLM analysis completed for %s %s", signal.symbol, signal.timeframe)
        return content
