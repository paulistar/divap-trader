# IQ Option — configuração OTC (perfil `otc`)

O perfil **OTC** é **isolado do DIVAP**: não participa do scan periódico Binance. Toda configuração exclusiva está em `src/profiles/otc.yaml` (bloco `otc:`).

## Conexão recomendada: MCP oficial

A IQ Option expõe um servidor **MCP** (Model Context Protocol) para opções digitais — **sem SMS/2FA**, com token Bearer.

1. No app ou web IQ Option: **Settings → AI integrations → Add**
2. Dê um nome, defina expiração e marque **Trade · Digital Options** se quiser ordens reais
3. Copie o token (só aparece uma vez)
4. Cole no Easypanel como `IQOPTION_MCP_TOKEN`

Documentação: https://iqoptionmcp.com/

| Servidor MCP | URL |
|--------------|-----|
| Digital Options (OTC/binárias) | `https://digital-options.mcp.iqoption.com` |
| Margin CFD | `https://marginal-cfd.mcp.iqoption.com` |
| Margin Crypto | `https://marginal-crypto.mcp.iqoption.com` |
| Margin Forex | `https://marginal-forex.mcp.iqoption.com` |

Um único token funciona nos quatro servidores. O perfil OTC usa apenas **digital-options**.

## Variáveis de ambiente

No **Easypanel Compose**, copie o bloco de `deploy/easypanel-iqoption.env.snippet`:

[Painel Environment — divap-trader](https://painel.martstudiosbr.com.br/projects/martstudios/compose/divap-trader/environment)

```env
IQOPTION_MCP_TOKEN=seu_token_aqui
IQOPTION_MCP_URL=https://digital-options.mcp.iqoption.com
IQOPTION_ACCOUNT_MODE=PRACTICE
OTC_TRADING_ENABLED=false
```

Salve, ligue **Create .env file** se estiver off, e faça **Deploy**.

| Variável | Descrição |
|----------|-----------|
| `IQOPTION_MCP_TOKEN` | Bearer token (Settings → AI integrations) |
| `IQOPTION_MCP_URL` | Endpoint MCP digital-options (default acima) |
| `IQOPTION_ACCOUNT_MODE` | `PRACTICE` (demo/training) ou `REAL` |
| `OTC_TRADING_ENABLED` | `true` para ordens reais (respeita `dry_run` no YAML) |

### Legado (opcional)

Email/senha via `iqoptionapi` não oficial — pode exigir **SMS 2FA** e falhar em automação:

```env
IQOPTION_EMAIL=...
IQOPTION_PASSWORD=...
```

Se `IQOPTION_MCP_TOKEN` estiver definido, o MCP tem **prioridade** sobre email/senha.

## Configuração do perfil (`src/profiles/otc.yaml`)

| Campo | Função |
|-------|--------|
| `otc.dry_run` | `true` = simula ordens sem enviar à corretora |
| `otc.default_stake_usd` | Valor por entrada (US$) |
| `otc.expiry_minutes` | Expiração padrão (1 = M1) |
| `otc.martingale` | Proteções (multiplicador por nível) |
| `otc.assets` | Ativos OTC permitidos (nomes IQ Option MCP) |
| `otc.asset_aliases` | Mapeia nomes do Telegram → IQ Option |
| `otc.telegram` | Listener futuro do canal de sinais |

Nomes reais no MCP (exemplos): `Ripple (OTC)`, `BTC/USD (OTC)`, `CARDANO (OTC)`.

## Testar conexão

```bash
python scripts/iqoption_test_connection.py
```

Resposta esperada com MCP:

```
OK — IQ Option conectada via mcp (modo PRACTICE)
MCP mode: read-write
Saldo: $8260.10
```

## Painel

- `GET /dashboard/otc/status` — saldo, transport (`mcp`/`legacy`), dry-run, conexão
- `POST /dashboard/otc/signal` — enviar texto de sinal (parser Telegram) ou campos manuais

## Ativar perfil OTC no painel

Em **Gestão da banca**, marque o checkbox **OTC — IQ Option** junto com os perfis DIVAP desejados. O OTC **não** dispara scan DIVAP; só fica disponível para execução OTC.

## Cursor (desenvolvimento local)

Adicione em `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "digital-options": {
      "url": "https://digital-options.mcp.iqoption.com",
      "headers": { "Authorization": "Bearer SEU_TOKEN" }
    }
  }
}
```

Reinicie o Cursor. O assistente pode usar `list_balances`, `list_assets`, `place_trade`, etc.

## Dependências legadas (opcional)

Só necessárias se usar email/senha em vez de MCP:

```bash
pip install websocket-client==0.56
pip install git+https://github.com/Lu-Yi-Hsun/iqoptionapi.git
```

## Próximos passos

1. Configurar `IQOPTION_MCP_TOKEN` no Easypanel
2. Validar `scripts/iqoption_test_connection.py`
3. Testar sinal manual via dashboard (`dry_run: true`)
4. Listener Telegram automático (`otc.telegram.enabled: true` + serviço `otc-telegram`)

### Telegram automático (sinais da sala)

1. Crie um bot com [@BotFather](https://t.me/BotFather) (ou use o `TELEGRAM_BOT_TOKEN` existente).
2. **Desative privacy mode**: `/setprivacy` → bot → **Disable** (senão o bot não lê todas as mensagens do grupo).
3. **Adicione o bot ao grupo/canal de sinais** como membro.
4. Descubra o **chat_id** do grupo (ex.: `-1001234567890`) com [@userinfobot](https://t.me/userinfobot) ou enviando uma mensagem e consultando `getUpdates`.
5. No Easypanel, configure:
   - `OTC_TELEGRAM_CHAT_ID=-1001234567890`
   - `OTC_TRADING_ENABLED=true`
6. Deploy inclui o serviço **`otc-telegram`**, que faz long-polling e enfileira sinais no Celery no instante em que a mensagem chega.

O listener ignora mensagens que não são sinais (`ENTRADA CONFIRMADA` + ativo + direção) e deduplica por `message_id` no Redis.
