#!/usr/bin/env bash
# Dispara deploy canônico via container Easypanel (sidecar VPS / SSH).
# Não faz git pull nos app containers — rebuild a partir do checkout do painel.
set -euo pipefail

EASYPANEL_CONTAINER="${EASYPANEL_CONTAINER:-}"
EASYPANEL_PROJECT="${EASYPANEL_PROJECT:-martstudios}"
EASYPANEL_SERVICE="${EASYPANEL_SERVICE:-divap-trader}"
CODE_DIR="/etc/easypanel/projects/${EASYPANEL_PROJECT}/${EASYPANEL_SERVICE}/code"

if [[ -z "${EASYPANEL_CONTAINER}" ]]; then
  EASYPANEL_CONTAINER="$(docker ps --format '{{.Names}}' | grep -E '^easypanel\\.' | head -1 || true)"
fi

if [[ -z "${EASYPANEL_CONTAINER}" ]]; then
  echo "ERRO: container Easypanel não encontrado (esperado easypanel.*)." >&2
  exit 1
fi

echo "Easypanel container: ${EASYPANEL_CONTAINER}"
echo "Code dir: ${CODE_DIR}"

docker exec "${EASYPANEL_CONTAINER}" sh -c "
  set -euo pipefail
  cd '${CODE_DIR}'
  chmod +x scripts/deploy-easypanel.sh
  exec ./scripts/deploy-easypanel.sh
"
