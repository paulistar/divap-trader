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
