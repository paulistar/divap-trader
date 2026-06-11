# Arquitetura — DIVAP Trader

## Visão geral

```
Binance (REST) → Ingestão → TimescaleDB
                    ↓
              Indicadores (RSI, Vol, Fibo, Padrões)
                    ↓
              Scanner DIVAP (D-V-A-P)
                    ↓
         Market Context (Fear&Greed, macro, HTF, news)
                    ↓
         ┌──────────┴──────────┐
         ↓                     ↓
    LLM Analyzer          Telegram Alerts
         ↓                     ↓
    FastAPI (/alerts, /analyze)
```

## Camadas

| Camada | Responsabilidade |
|--------|------------------|
| `data/` | Coleta OHLCV, persistência, cache Redis |
| `indicators/` | Cálculos técnicos puros (sem lógica de negócio) |
| `detection/` | Orquestra critérios DIVAP → `DIVAPSignal` |
| `context/` | Sentimento, Fear & Greed, macro, notícias, score pré-LLM |
| `analysis/` | Validação qualitativa via GPT-4o (setup + contexto Apolo) |
| `alerts/` | Formatação e envio Telegram; Celery Beat |
| `execution/` | Stubs Fase 3 (broker, risk manager) |
| `api/` | REST com envelope `{ success, data, error, meta }` |

## Segurança

- `GET /health` — público
- Demais rotas exigem `X-API-Key` quando `APP_ENV=production`
- Postgres/Redis apenas rede Docker em produção (`docker-compose.prod.yml`)

## Infraestrutura

- **app** — FastAPI (porta 8000)
- **worker** — Celery worker
- **beat** — Celery Beat (scan periódico)
- **postgres** — TimescaleDB
- **redis** — broker Celery + cache

## ADRs

Ver `docs/adr/` para decisões arquiteturais documentadas.
