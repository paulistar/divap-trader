#!/usr/bin/env bash
# Deploy DIVAP Trader na VPS — trade.martstudiosbr.com.br:80
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/divap-trader}"
DOMAIN="trade.martstudiosbr.com.br"

echo "=== Deploy DIVAP Trader ==="
echo "Diretório: $APP_DIR"
echo "Domínio:   https://$DOMAIN"

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "ERRO: $APP_DIR/.env não encontrado. Copie .env.example e configure."
  exit 1
fi

cd "$APP_DIR"

echo "[1/4] Build e start Docker..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

echo "[2/4] Init database..."
docker compose exec -T app python scripts/init_db.py

echo "[3/4] Reverse proxy..."
if command -v caddy &>/dev/null && ! ss -tlnp 2>/dev/null | grep -q ':80.*node'; then
  sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
  sudo systemctl reload caddy || sudo systemctl restart caddy
  echo "Caddy recarregado."
else
  echo "AVISO: porta 80 ocupada (Easypanel?) — configure domínio no painel:"
  echo "  trade.martstudiosbr.com.br → app:8000 (ver docs/DEPLOY.md)"
fi

echo "[4/4] Smoke test..."
sleep 3
BASE_URL="http://127.0.0.1:8000" ./scripts/smoke_test.sh || true

echo ""
echo "=== Deploy concluído ==="
echo "Configure Cloudflare: A record 'trade' → IP desta VPS (proxied)"
echo "Teste externo: BASE_URL=https://$DOMAIN API_KEY=<sua-chave> ./scripts/smoke_test.sh"
