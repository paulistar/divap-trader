# DIVAP Trader

Sistema inteligente de investimento baseado na metodologia **DIVAP** (Divergência IFR + Volume + Alvo Fibonacci + Padrão de reversão).

| Fase | Status |
|------|--------|
| **Fase 2** — Análise assistida por IA + alertas Telegram | ✅ MVP |
| **Fase 3** — Execução automatizada | Roadmap |

## Stack

- Python 3.11, FastAPI, Celery
- PostgreSQL + TimescaleDB, Redis
- Binance (ccxt), OpenAI GPT-4o, Telegram Bot API
- Docker Compose → VPS + Cloudflare

## Início rápido (local)

```bash
cp .env.example .env
# APP_ENV=development (sem API key obrigatória)

docker compose up -d --build
docker compose exec app python scripts/init_db.py

curl http://localhost:8000/health
curl -X POST "http://localhost:8000/analyze/BTCUSDT?timeframe=4h&with_llm=false"
```

## Desenvolvimento

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export PYTHONPATH=.
uvicorn src.api.main:app --reload
pytest
```

## API

| Endpoint | Descrição |
|----------|-----------|
| `GET /health` | Health check (público) |
| `POST /analyze/{symbol}` | Scan DIVAP + IA opcional |
| `POST /analyze/scan/all` | Scan completo |
| `GET /alerts` | Lista alertas |
| `GET /analysis/{id}` | Análise IA do alerta |
| `GET /signals/history` | Histórico |

Em produção (`APP_ENV=production`), envie header `X-API-Key`.

Documentação completa: [docs/API.md](docs/API.md)

## Deploy produção

Domínio: **https://trade.martstudiosbr.com.br** (origem VPS porta 80 + Cloudflare)

Ver [docs/DEPLOY.md](docs/DEPLOY.md).

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
BASE_URL=https://trade.martstudiosbr.com.br API_KEY=sua-chave ./scripts/smoke_test.sh
```

## Estrutura

```
src/
├── core/        # Config, constants, Celery
├── data/        # Binance, models, repositories
├── indicators/  # RSI, volume, Fibonacci, padrões
├── detection/   # Scanner DIVAP
├── analysis/    # LLM + prompts Apolo
├── alerts/      # Telegram + scheduler
└── api/         # FastAPI
```

## Skills Cursor

- `divap-trading-system` — regras DIVAP
- `cto-architect`, `caio-architect`, `cio-engineer` — arquitetura, IA, segurança

Ver [AGENTS.md](AGENTS.md).

## Documentação

- [Arquitetura](docs/ARCHITECTURE.md)
- [Regras DIVAP](docs/DIVAP_RULES.md)
- [Deploy](docs/DEPLOY.md)
- [ADRs](docs/adr/)
