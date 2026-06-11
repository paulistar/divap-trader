# ADR 005: Multi-market — Crypto (Binance) + Forex (OANDA)

**Status:** Aceito  
**Data:** 2026-06-10

## Contexto

Operação atual é 100% crypto spot na Binance. Objetivo: operar **cripto e Forex** com a mesma metodologia DIVAP, sem misturar risco, PnL ou execução entre mercados.

## Decisão

1. Introduzir `Market` (`crypto`, `forex`) e `Venue` (`binance`, `oanda`) em `src/markets/`.
2. `Instrument` identifica `{market, venue, symbol}` em alertas e trades.
3. Abstrair `MarketDataSource` (alias de `ExchangeSource`) e `ExecutionBroker`.
4. Factory `get_data_source(venue)` / `get_broker(venue)` — MVP crypto via Binance.
5. Colunas `market` e `venue` em `alerts` e `trades` (default `crypto` / `binance`).
6. **Forex execução:** OANDA practice na Fase 2–4 do roadmap; dados OANDA na Fase 2.

## Pares Forex iniciais (Fase 2)

`EUR_USD`, `GBP_USD`, `USD_JPY`, `XAU_USD`

## Consequências

- Positivo: scanner DIVAP reutilizável; crypto inalterado com defaults.
- Positivo: PnL e stats podem filtrar por mercado.
- Negativo: migration DB; executor deixa de referenciar Binance diretamente.
- iPhone/PWA e gates FX ficam para fases seguintes do roadmap.

## Referência

`docs/plans/2026-06-10-crypto-forex-roadmap.md`
