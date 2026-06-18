# IQ Option — configuração OTC (perfil `otc`)

O perfil **OTC** é **isolado do DIVAP**: não participa do scan periódico Binance. Toda configuração exclusiva está em `src/profiles/otc.yaml` (bloco `otc:`).

## Conta

1. Use **conta demo/prática** (`IQOPTION_ACCOUNT_MODE=PRACTICE`).
2. A biblioteca `iqoptionapi` é **não oficial** — IQ Option pode bloquear automação em conta real.
3. Nunca commite e-mail/senha no repositório.

## Variáveis de ambiente

```env
IQOPTION_EMAIL=seu@email.com
IQOPTION_PASSWORD=sua_senha
IQOPTION_ACCOUNT_MODE=PRACTICE
OTC_TRADING_ENABLED=false
```

| Variável | Descrição |
|----------|-----------|
| `IQOPTION_EMAIL` | Login IQ Option |
| `IQOPTION_PASSWORD` | Senha IQ Option |
| `IQOPTION_ACCOUNT_MODE` | `PRACTICE` (demo) ou `REAL` |
| `OTC_TRADING_ENABLED` | `true` para ordens reais na IQ (respeita `dry_run` no YAML) |

## Configuração do perfil (`src/profiles/otc.yaml`)

| Campo | Função |
|-------|--------|
| `otc.dry_run` | `true` = simula ordens sem enviar à corretora |
| `otc.default_stake_usd` | Valor por entrada (US$) |
| `otc.expiry_minutes` | Expiração padrão (1 = M1) |
| `otc.martingale` | Proteções (multiplicador por nível) |
| `otc.assets` | Ativos OTC permitidos na IQ |
| `otc.asset_aliases` | Mapeia nomes do Telegram → IQ Option |
| `otc.telegram` | Listener futuro do canal de sinais |

## Testar conexão

```bash
python scripts/iqoption_test_connection.py
```

## Painel

- `GET /dashboard/otc/status` — saldo, modo, dry-run, conexão
- `POST /dashboard/otc/signal` — enviar texto de sinal (parser Telegram) ou campos manuais

## Ativar perfil OTC no painel

Em **Gestão da banca**, marque o checkbox **OTC — IQ Option** junto com os perfis DIVAP desejados. O OTC **não** dispara scan DIVAP; só fica disponível para execução OTC.

## Dependências

```bash
pip install websocket-client==0.56
pip install git+https://github.com/Lu-Yi-Hsun/iqoptionapi.git
```

Já listadas em `requirements.txt`.

## Próximos passos

1. Configurar credenciais demo no Easypanel
2. Validar `scripts/iqoption_test_connection.py`
3. Testar sinal manual via dashboard (`dry_run: true`)
4. Listener Telegram (quando `otc.telegram.enabled: true`)
