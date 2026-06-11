"""LLM-generated profile insights (Fase D) — cached, optional."""

from __future__ import annotations

import json
import logging
from hashlib import sha256

from openai import OpenAI

from src.core.config import settings
from src.core.dashboard_cache import cache_get, cache_set
from src.core.exceptions import AnalysisError
from src.profiles.models import ProfileSnapshot

logger = logging.getLogger(__name__)

INSIGHTS_CACHE_PREFIX = "divap:profile_insights:"
INSIGHTS_TTL_SECONDS = 900


def _market_fingerprint(market: dict) -> str:
    payload = json.dumps(market, sort_keys=True, default=str)
    return sha256(payload.encode()).hexdigest()[:16]


def _build_prompt(
    market: dict,
    snapshots: list[ProfileSnapshot],
    *,
    active_profile_id: str,
    goal_reached: bool,
) -> str:
    profiles_block = []
    for snap in snapshots:
        a = snap.assessment
        profiles_block.append(
            f"- {snap.profile.name} ({snap.profile.id}): fit={a.fit_score}% "
            f"status={a.status}; regras: {a.detail}; tagline: {snap.profile.tagline}"
        )

    return f"""Contexto de mercado agora:
- Fear & Greed: {market.get('fear_greed')}
- Veredito dominante: {market.get('dominant_verdict')}
- Score médio contexto: {market.get('avg_context_score')}
- BTC dominância: {market.get('btc_dominance_pct')}%
- Mercado 24h: {market.get('market_cap_change_24h_pct')}%
- Perfil ativo na execução: {active_profile_id}
- Meta mensal atingida (modo protegido): {'sim' if goal_reached else 'não'}

Perfis (avaliação rule-based):
{chr(10).join(profiles_block)}

Responda APENAS JSON válido, chaves: divap, conservador, caixa_rapido, agressivo.
Cada valor: 1-2 frases em português, direto, para o trader — se é bom momento para aquele estilo AGORA e por quê.
Não repita números mecanicamente; interprete para leigos."""


def _parse_insights(raw: str) -> dict[str, str]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise AnalysisError("LLM insights response is not a JSON object")
    return {str(k): str(v) for k, v in data.items()}


def generate_profile_insights(
    market: dict,
    snapshots: list[ProfileSnapshot],
    *,
    active_profile_id: str,
    goal_reached: bool = False,
) -> dict[str, str]:
    if not settings.openai_api_key:
        return {}

    cache_key = INSIGHTS_CACHE_PREFIX + _market_fingerprint(market)
    cached = cache_get(cache_key)
    if cached is not None:
        return {str(k): str(v) for k, v in cached.items()}

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = _build_prompt(
        market,
        snapshots,
        active_profile_id=active_profile_id,
        goal_reached=goal_reached,
    )

    try:
        response = client.chat.completions.create(
            model=settings.openai_model_triage,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é um advisor de trading crypto. Respostas curtas, "
                        "práticas, em português do Brasil. Só JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=600,
        )
        content = response.choices[0].message.content
        if not content:
            return {}
        insights = _parse_insights(content)
        cache_set(cache_key, insights, INSIGHTS_TTL_SECONDS)
        return insights
    except Exception as exc:
        logger.warning("Profile LLM insights failed: %s", exc)
        return {}
