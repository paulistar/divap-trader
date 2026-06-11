#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-}"

echo "=== DIVAP Trader Smoke Test ==="
echo "Base URL: $BASE_URL"

echo ""
echo "[1/3] Health check..."
for i in 1 2 3 4 5; do
  if curl -sf "$BASE_URL/health" | grep -q '"status":"ok"'; then
    echo "OK"
    break
  fi
  if [[ $i -eq 5 ]]; then
    echo "FAIL: health check (servidor rodando em $BASE_URL?)"
    exit 1
  fi
  sleep 2
done

HEADERS=()
if [[ -n "$API_KEY" ]]; then
  HEADERS=(-H "X-API-Key: $API_KEY")
fi

echo ""
echo "[2/3] Analyze BTCUSDT (sem LLM)..."
RESPONSE=$(curl -sf "${HEADERS[@]}" -X POST \
  "$BASE_URL/analyze/BTCUSDT?timeframe=4h&with_llm=false")
echo "$RESPONSE" | grep -q '"success":true' && echo "OK" || {
  echo "FAIL: analyze endpoint"
  echo "$RESPONSE"
  exit 1
}

echo ""
echo "[3/3] List alerts..."
curl -sf "${HEADERS[@]}" "$BASE_URL/alerts?limit=5" | grep -q '"success":true' && echo "OK" || {
  echo "FAIL: alerts endpoint"
  exit 1
}

echo ""
echo "=== All smoke tests passed ==="
