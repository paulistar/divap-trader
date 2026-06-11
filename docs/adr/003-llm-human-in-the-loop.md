# ADR 003: LLM human-in-the-loop (Fase 2)

**Status:** Aceito  
**Data:** 2026-06-10

## Contexto

Fase 2 é análise assistida por IA, não execução automática. Risco de alucinação em níveis de preço.

## Decisão

- Scanner calcula critérios D-V-A-P **antes** da IA
- LLM recebe JSON estruturado; **proibido inventar números**
- LLM só dispara quando scanner ≥ 3 confluências
- GPT-4o para análise; gpt-4o-mini opcional para triagem
- Fase 3 exige validação humana antes de ordem

## Consequências

- Positivo: reduz alucinação; custo OpenAI controlado
- Negativo: workflow Apolo com print de gráfico fica para Fase 2+
