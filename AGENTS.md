# DIVAP Trader — Guia para Agentes Cursor

## Skills obrigatórias

| Skill | Quando invocar |
|-------|----------------|
| `divap-trading-system` | Indicadores, scanner DIVAP, regras de confluência, prompts, validação de setups |
| `cto-architect` | Decisões de arquitetura, ADRs, trade-offs de stack |
| `caio-architect` | Integração LLM, guardrails, quando chamar GPT |
| `cio-engineer` | Deploy VPS, Cloudflare, secrets, segurança |
| `mart-art` | Dashboard SvelteKit (pós-MVP) |

## Fonte de conhecimento DIVAP

Skill global: `~/.cursor/skills/divap-trading-system/`

- `references/` — regras operacionais
- `knowledge/raw/` — transcrições dos materiais do curso

Espelho no repo: `docs/DIVAP_RULES.md`

## Convenções de código

- **Imutabilidade** — não mutar candles/sinais; retornar novos objetos
- **Repository pattern** — acesso a dados via `src/data/repositories/`
- **Envelope API** — `{ success, data, error, meta }`
- **Testes** — TDD para indicadores e scanner (Sprints 2–3)

## Fases

- **Fase 2 (MVP):** análise assistida por IA + alertas Telegram
- **Fase 3 (roadmap):** execução automatizada com validação humana
