#!/usr/bin/env bash
# Deploy canônico DIVAP Trader no Easypanel (martstudios/divap-trader).
#
# Executar SEMPRE a partir do checkout do Easypanel no host (git pull + rebuild).
# Não use git pull dentro de containers em execução — a imagem é COPY no build.
#
# Onde rodar:
#   1) Container Easypanel (tem docker + /etc/easypanel/...):
#        cd /etc/easypanel/projects/martstudios/divap-trader/code
#        ./scripts/deploy-easypanel.sh
#   2) Via sidecar/MCP na VPS:
#        ./scripts/trigger-easypanel-deploy.sh
#
set -euo pipefail

EASYPANEL_PROJECT="${EASYPANEL_PROJECT:-martstudios}"
EASYPANEL_SERVICE="${EASYPANEL_SERVICE:-divap-trader}"
CODE_DIR="${EASYPANEL_CODE_DIR:-/etc/easypanel/projects/${EASYPANEL_PROJECT}/${EASYPANEL_SERVICE}/code}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-${EASYPANEL_PROJECT}_${EASYPANEL_SERVICE}}"
GIT_REF="${GIT_REF:-main}"
SKIP_GIT_PULL="${SKIP_GIT_PULL:-0}"
SKIP_INIT_DB="${SKIP_INIT_DB:-0}"
SKIP_HEALTH="${SKIP_HEALTH:-0}"

compose_files=(-f docker-compose.easypanel.yml)
if [[ -f "${CODE_DIR}/docker-compose.override.yml" ]]; then
  compose_files+=(-f docker-compose.override.yml)
fi

compose() {
  docker compose -p "${COMPOSE_PROJECT}" "${compose_files[@]}" "$@"
}

echo "=== Easypanel deploy: ${EASYPANEL_PROJECT}/${EASYPANEL_SERVICE} ==="
echo "Code dir:        ${CODE_DIR}"
echo "Compose project: ${COMPOSE_PROJECT}"

if [[ ! -d "${CODE_DIR}" ]]; then
  echo "ERRO: diretório do Easypanel não encontrado: ${CODE_DIR}" >&2
  echo "Use trigger-easypanel-deploy.sh a partir da VPS ou o botão Deploy no painel." >&2
  exit 1
fi

cd "${CODE_DIR}"

if [[ "${SKIP_GIT_PULL}" != "1" ]]; then
  echo "[1/4] Git pull (${GIT_REF})..."
  git fetch origin "${GIT_REF}"
  git checkout "${GIT_REF}"
  git pull --ff-only origin "${GIT_REF}"
else
  echo "[1/4] Git pull ignorado (SKIP_GIT_PULL=1)"
fi

echo "Commit: $(git rev-parse --short HEAD) — $(git log -1 --format='%s')"

echo "[2/4] Build e recreate containers..."
compose up -d --build --remove-orphans

if [[ "${SKIP_INIT_DB}" != "1" ]]; then
  echo "[3/4] Migração idempotente (init_db)..."
  compose exec -T app python scripts/init_db.py
else
  echo "[3/4] init_db ignorado (SKIP_INIT_DB=1)"
fi

if [[ "${SKIP_HEALTH}" != "1" ]]; then
  echo "[4/4] Health check..."
  sleep 5
  compose exec -T app python -c "
import urllib.request
r = urllib.request.urlopen('http://127.0.0.1:80/health', timeout=15)
body = r.read().decode()
assert r.status == 200, r.status
assert '\"status\":\"ok\"' in body or '\"status\": \"ok\"' in body, body[:200]
print('OK', body[:120])
"
else
  echo "[4/4] Health check ignorado (SKIP_HEALTH=1)"
fi

echo ""
echo "=== Deploy concluído ==="
compose ps
