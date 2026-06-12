from __future__ import annotations

from src.profiles.models import ProfileAssessment, ProfileSnapshot, TradingProfile


def _status_from_score(score: int) -> str:
    if score >= 75:
        return "otimo"
    if score >= 55:
        return "bom"
    if score >= 35:
        return "neutro"
    return "ruim"


def _headline_for_status(profile: TradingProfile, status: str) -> str:
    labels = {
        "otimo": f"Bom momento para {profile.name}",
        "bom": f"Razoável para {profile.name}",
        "neutro": f"Neutro — {profile.name} com cautela",
        "ruim": f"Ruim para {profile.name} agora",
    }
    return labels.get(status, profile.name)


def assess_profile(
    profile: TradingProfile,
    market: dict,
    *,
    active_profile_id: str,
) -> ProfileAssessment:
    rules = profile.advisor
    score = 50
    notes: list[str] = []

    fg = market.get("fear_greed")
    if fg is not None:
        if rules.ideal_fear_greed_min <= fg <= rules.ideal_fear_greed_max:
            score += 12
            notes.append(f"Fear & Greed {fg} na faixa ideal")
        elif fg < 15:
            score -= 8
            notes.append("Medo extremo — volatilidade imprevisível")
        elif fg > 85:
            score -= 5
            notes.append("Euforia — risco de reversão")

    verdict = market.get("dominant_verdict") or "unknown"
    if verdict in rules.preferred_verdicts:
        score += 18
        notes.append(f"Veredito {verdict} alinhado")
    elif verdict == "reject":
        score -= 22
        notes.append("Contexto reject nos pares")
    else:
        score -= 6

    avg_score = market.get("avg_context_score")
    if avg_score is not None:
        if avg_score >= rules.min_avg_score:
            score += 10
        else:
            score -= 12
            notes.append(f"Score médio {avg_score} abaixo do ideal ({rules.min_avg_score})")

    change = market.get("market_cap_change_24h_pct")
    if change is not None:
        abs_change = abs(float(change))
        if rules.volatility == "high" and abs_change >= 2.0:
            score += 10
            notes.append("Volatilidade 24h favorece giro")
        elif rules.volatility == "low" and abs_change >= 4.0:
            score -= 10
            notes.append("Mercado agitado demais para perfil conservador")
        elif rules.needs_momentum and abs_change < 1.0:
            score -= 14
            notes.append("Pouco movimento para caixa rápido")

    if rules.needs_momentum and verdict == "confirm" and (change is None or abs(float(change)) >= 1.5):
        score += 8

    if profile.id == "anti_divap" and fg is not None:
        if fg <= 20 or fg >= 80:
            score += 15
            notes.append(f"Extremo F&G {fg} — favorável ao contrarian")
        elif 45 <= fg <= 55:
            score -= 10
            notes.append("Sentimento neutro — pouco edge contrarian")

    score = max(0, min(100, score))
    status = _status_from_score(score)
    detail = ". ".join(notes) if notes else profile.description

    return ProfileAssessment(
        profile_id=profile.id,
        fit_score=score,
        status=status,
        headline=_headline_for_status(profile, status),
        detail=detail,
        is_active=profile.id == active_profile_id,
    )


def assess_all_profiles(market: dict, active_profile_id: str) -> list[ProfileSnapshot]:
    from src.profiles.loader import load_all_profiles

    snapshots: list[ProfileSnapshot] = []
    for profile in load_all_profiles():
        assessment = assess_profile(profile, market, active_profile_id=active_profile_id)
        snapshots.append(ProfileSnapshot(profile=profile, assessment=assessment))
    return snapshots
