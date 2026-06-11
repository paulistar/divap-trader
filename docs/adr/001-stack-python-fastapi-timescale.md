# ADR 001: Stack Python + FastAPI + TimescaleDB

**Status:** Aceito  
**Data:** 2026-06-10

## Contexto

Sistema DIVAP Fase 2 precisa de: ingestão OHLCV, cálculos técnicos, scanner, LLM, alertas e API REST. Deploy em VPS própria com Cloudflare.

## Decisão

- **Python 3.11+** — ecossistema maduro para TA (pandas, pandas-ta) e IA
- **FastAPI** — API assíncrona, OpenAPI automático
- **TimescaleDB** — séries temporais para candles e histórico de sinais
- **Redis + Celery** — tarefas assíncronas e scan periódico
- **Docker Compose** — orquestração na VPS

## Alternativas consideradas

- Node.js/TypeScript — menos bibliotecas de TA maduras
- SQLite — insuficiente para multi-timeframe + backtest
- Flask — sem async nativo

## Consequências

- Positivo: stack alinhada ao spec DIVAP; fácil evolução para Fase 3
- Negativo: operar Postgres + Celery exige mais ops que monólito simples
