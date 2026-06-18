# Deploy — VPS Mart Studios + Cloudflare

**Domínio:** `https://trade.martstudiosbr.com.br`  
**Porta pública:** 80/443 (via Cloudflare + Easypanel Traefik)  
**App interna:** porta 80 no container (padrão Easypanel Mart Studios)

## Arquitetura na VPS

A VPS Mart Studios já usa **Easypanel** com Traefik na porta **80**. Não instale Caddy separado — conflita com o painel.

```
Visitante → Cloudflare (HTTPS :443)
         → VPS :80 (Easypanel / Traefik)
         → container app :80 (FastAPI)
```

Outros subdomínios seguem o mesmo padrão (`chat.`, `mcp.`, `vps.`).

---

## Opção A — Easypanel (recomendado)

### 1. Publicar código no GitHub

```bash
# No Mac, após commit
gh repo create paulistar/divap-trader --private --source=. --remote=origin
git push -u origin main
```

### 2. Criar serviço Compose no Easypanel

- **Projeto:** `martstudios`
- **Serviço:** `divap-trader` (tipo Compose)
- **Source:** GitHub `paulistar/divap-trader`, branch `main`
- **Compose file:** `docker-compose.easypanel.yml`

### 3. Variáveis de ambiente (painel Easypanel)

No serviço **Compose**, o Easypanel usa um **textarea manual** na aba **Environment** — **não** importa variáveis do `docker-compose.easypanel.yml` sozinhas. Você precisa colar/editar lá.

Arquivo pronto para copiar (IQ Option): `deploy/easypanel-iqoption.env.snippet`

```env
APP_ENV=production
APP_DEBUG=false
API_KEY=<chave-forte-aleatoria>
POSTGRES_PASSWORD=<senha-forte>
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
BINANCE_USE_TESTNET=false
```

**OTC — IQ Option (cole no final do Environment):**

```env
IQOPTION_EMAIL=seu@email.com
IQOPTION_PASSWORD=sua_senha
IQOPTION_ACCOUNT_MODE=PRACTICE
OTC_TRADING_ENABLED=false
```

> Ative **Create .env file** (toggle) se ainda não estiver ligado — o compose usa `env_file: .env`.

### 4. Domínio no Easypanel

| Campo | Valor |
|-------|-------|
| Host | `trade.martstudiosbr.com.br` |
| HTTPS | Ativado |
| Porta do container | **80** |
| Serviço Compose | **app** (`composeService` no domínio Easypanel) |
| Protocolo interno | HTTP |

### 5. Init do banco (após primeiro deploy)

```bash
# Via terminal do serviço app no Easypanel, ou SSH na VPS:
docker exec -it <container-app> python scripts/init_db.py
```

### 6. Cloudflare DNS

| Tipo | Nome | Conteúdo | Proxy |
|------|------|----------|-------|
| A | trade | IP da VPS | Proxied (laranja) |

**SSL/TLS:** Flexible ou Full (Easypanel já termina TLS no Traefik).

---

## Opção B — Docker manual na VPS (sem Easypanel)

Use apenas se a VPS **não** tiver Easypanel na :80.

```bash
git clone <repo> /opt/divap-trader
cd /opt/divap-trader
cp .env.example .env
nano .env

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec app python scripts/init_db.py

# Caddy na :80 (ver deploy/Caddyfile)
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Ou use o script:

```bash
./scripts/deploy-vps.sh
```

---

## Smoke test

```bash
# Local
./scripts/smoke_test.sh

# Produção
BASE_URL=https://trade.martstudiosbr.com.br API_KEY=sua-chave ./scripts/smoke_test.sh
```

## Monitoramento

```bash
docker compose logs -f app worker beat
docker compose ps
```

## Celery Beat

Scan automático a cada 15 min nos timeframes prioritários (1h, 4h, 1d).

## Atenção

- Disco da VPS estava em ~89% — limpe imagens antigas antes do deploy (`docker system prune`)
- Postgres e Redis **não** devem ter portas públicas
- `API_KEY` obrigatória quando `APP_ENV=production`
