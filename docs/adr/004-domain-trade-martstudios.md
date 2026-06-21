# ADR 004: Domínio trade.martstudiosbr.com.br porta 80

**Status:** Aceito  
**Data:** 2026-06-11

## Contexto

Deploy na VPS Mart Studios com Cloudflare na frente. Domínio definido pelo operador.

## Decisão

- **Domínio:** `trade.martstudiosbr.com.br`
- **Porta pública:** **80/443** (Easypanel Traefik na VPS — mesma infra de `chat.`, `mcp.`, etc.)
- **App Docker:** porta **80** no container (mesmo padrão de `chat.`, `mcp.`, `vps.`)
- **Easypanel (painel):** porta **8000** (UI administrativa, separada dos apps)
- **Cloudflare:** registro A `trade` → IP VPS, proxy ativado
- **SSL:** Cloudflare + Traefik Easypanel (visitante sempre HTTPS)
- **Caddy standalone:** apenas fallback se VPS sem Easypanel (`deploy/Caddyfile`)

## Consequências

- Positivo: alinhado à infra Mart Studios existente, sem conflito na :80
- Positivo: deploy via Compose no projeto `martstudios` do Easypanel
- Negativo: depende do painel Easypanel para roteamento de domínio
- Auto-deploy: GitHub Actions (`.github/workflows/ci.yml`) + webhook `EASYPANEL_DEPLOY_WEBHOOK_URL`; fallback manual via `scripts/deploy-easypanel.sh`
