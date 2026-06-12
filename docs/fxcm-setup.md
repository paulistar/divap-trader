# FXCM — configuração da API

A API REST da FXCM **não usa login/senha**. É necessário um **access token** gerado no Trading Station.

## 1. Gerar token (conta demo)

A FXCM migrou para [app.fxcm.com](https://app.fxcm.com/desktop/trading). O menu antigo **User Account → Token Management** **não aparece** na interface nova (só Settings / Help / About no dropdown da conta).

### Links documentados (todos apontam ao mesmo lugar hoje)

| Link | Status atual |
|------|----------------|
| [tradingstation.fxcm.com](https://tradingstation.fxcm.com/) | Redireciona para `app.fxcm.com` (sem Token Management) |
| [app.fxcm.com/desktop/trading](https://app.fxcm.com/desktop/trading) | Plataforma nova — login OK, sem menu de token |
| [app.fxcm.com/desktop/token-management](https://app.fxcm.com/desktop/token-management) | Rota legada — costuma mostrar *Session Ended* |
| [myfxcm.com](https://www.myfxcm.com/fxma/login) | Portal de conta — não gera token REST (demo) |
| [Download Trading Station Desktop](https://www.fxcm.com/markets/platforms/trading-station/download/) | **Melhor tentativa self-service** — app nativo pode ainda ter Token Management |
| [Documentação REST API](https://fxcm-rest.readthedocs.io/en/latest/socketrestapispecs.html) | Oficial — confirma token via Trading Station Web |
| [fxcmpy Quick Start](https://fxcmpy.tpq.io/00_quick_start.html) | Oficial — mesmo fluxo User Account → Token Management |

### Caminhos que funcionam na prática (2025/2026)

1. **Trading Station Desktop (Windows/Mac)** — instalar, login com `701913665`, procurar **User Account → Token Management** no menu superior (interface antiga embutida no app).
2. **E-mail para a FXCM** (mais confiável na web nova): `api@fxcm.com` com username `701913665`, account ID `1001985505`, pedindo ativação REST API + token ou link direto para Token Management.
3. **Suporte API** — página [API Trading](https://www.fxcm.com/markets/algorithmic-trading/api-trading/) cita suporte 24/5 em `api@fxcm.com`.

### Alternativa (não é o token REST / fxcmpy)

**ForexConnect** usa login + senha diretamente ([FIX / Java / ForexConnect](https://www.fxcm.com/markets/help/api-trading-what-api-interfaces-does-fxcm-have/)). Exige outro SDK — não serve para `fxcmpy` nem para o `FxcmSource` já implementado.

### OAuth terceiros

A FXCM tem fluxo [3rd-party OAuth](https://github.com/fxcm/3rd-party-oauth) para apps registrados (client_id/secret). Não substitui o token manual para uso pessoal sem cadastro na FXCM.

Quando obtiver o token (40 caracteres hex), copie **uma única vez** — não é possível recuperá-lo depois.

## 2. Variáveis de ambiente

```env
FXCM_ACCESS_TOKEN=seu_token_aqui
FXCM_SERVER=demo
# FXCM_ACCOUNT_ID=opcional — usa a primeira conta se omitido
```

## 3. Testar conexão

```bash
python scripts/fxcm_test_connection.py
```

## 4. Conta live

Contas reais precisam de e-mail para `api@fxcm.com` solicitando ativação da REST API.

## Segurança

- Nunca commite token, login ou senha no repositório
- Use apenas variáveis de ambiente (Easypanel / `.env` local)
- Troque a senha da conta se ela foi exposta em chat ou log
