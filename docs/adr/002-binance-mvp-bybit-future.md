# ADR 002: Binance no MVP, Bybit no roadmap

**Status:** Aceito  
**Data:** 2026-06-10

## Contexto

Material DIVAP/ APTC referencia TradingView + Bybit. Usuário escolheu Binance para MVP.

## Decisão

- MVP usa **Binance** via ccxt (`src/data/sources/binance.py`)
- Interface abstrata `ExchangeSource` permite adicionar **Bybit** na Fase 3
- Scanner e indicadores são agnósticos de exchange

## Consequências

- Positivo: API Binance madura; ccxt unifica REST
- Negativo: alertas APTC do Radar DIVAP são calibrados para Bybit — validar manualmente no MVP
