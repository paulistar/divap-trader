# API — DIVAP Trader

Base URL: `https://api.seudominio.com` (produção) ou `http://localhost:8000` (dev)

## Autenticação

Header `X-API-Key` em produção (atrás do Cloudflare).

## Envelope de resposta

```json
{
  "success": true,
  "data": { },
  "error": null,
  "meta": { }
}
```

## Endpoints

### `GET /health`

Health check.

### `GET /dashboard`

Painel web simples para acompanhar alertas, trades e métricas. Página pública; ao abrir, informe a `X-API-Key` (salva no navegador). Auto-refresh a cada 30s.

**Resposta:**
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "app_env": "development",
    "version": "0.1.0"
  },
  "error": null,
  "meta": {}
}
```

### `GET /context/{symbol}`

Contexto de mercado para validação pré-entrada (Fear & Greed, macro, HTF, notícias).

**Query:** `timeframe` (15m|1h|4h|1d), `direction` (buy|sell)

**Resposta `data`:** `fear_greed`, `global_market`, `htf_trends`, `macro_indices`, `news_headlines`, `context_score`, `context_verdict`, `risk_flags`

### `POST /analyze/{symbol}`

Scan manual de um ativo. Query: `timeframe` (15m|1h|4h|1d), `with_llm` (bool).

### `POST /analyze/scan/all`

Dispara scan completo (mesma lógica do Celery). Query: `notify` (bool).

### `GET /alerts`

Lista alertas DIVAP paginados. Query: `limit`, `offset`.

### `GET /alerts/{id}`

Detalhe de um alerta.

### `POST /alerts/{id}/acknowledge`

Marca alerta como visto.

### `GET /analysis/{alert_id}`

Análise IA vinculada ao alerta.

### `GET /signals/history`

Histórico de sinais (alias de `/alerts`).

### `GET /trades`

Lista trades executados (testnet/live). Query: `limit`, `offset`.

**Campos `data`:** `symbol`, `direction`, `status` (open|closed|simulated), `entry_price`, `exit_price`, `pnl_usdt`, `pnl_pct`, `close_reason`, `trading_mode`.

### `GET /trades/{id}`

Detalhe de um trade.

### `GET /stats`

Métricas agregadas de performance.

**Resposta `data`:** `closed_count`, `wins`, `losses`, `open_count`, `win_rate_pct`, `total_pnl_usdt`, `avg_pnl_pct`, `trading_enabled`, `trading_mode`.
