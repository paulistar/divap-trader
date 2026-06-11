# Regras DIVAP — Espelho Operacional

> Fonte primária: skill `divap-trading-system` → `references/`

## Acrônimo

**DIVAP** = **D**ivergência IFR + **V**olume + **A**lvo (Fibonacci) + **P**adrão de reversão

## Checklist de confluência

| Critério | Regra |
|----------|-------|
| D — Divergência | IFR(14): preço e indicador em direções opostas |
| V — Volume | Volume de **reversão** no nível (não confundir com rompimento) |
| A — Alvo Fibo | Extensão 2 pontos; priorizar 1.0 e 1.618 |
| P — Padrão | Candlestick (martelo, engolfo, estrela cadente, harami) e/ou gráfico |

Confirmação opcional: cruzamento MM 20/50.

## Regras de entrada (scanner)

| Confluências | Ação |
|--------------|------|
| ≤ 2 | Não gera alerta operacional |
| 3 | Alerta `low`/`medium` — reduzir % da banca |
| 4+ | Alerta `high` — entrada assertiva |

Divergência IFR é **obrigatória** em qualquer alerta.

## Gestão de risco por timeframe

| Timeframe | % banca por entrada |
|-----------|---------------------|
| 1h | 4–6% |
| 4h | 8–12% |
| Diário | 10–15% |
| 15m | 1–2% |

## Violinada

- Stop com folga (BTC: ~100–200 USD além do extremo)
- Reentrada se fechamento confirma reversão com confluências

## Implementação

| Módulo | Arquivo |
|--------|---------|
| Constantes | `src/core/constants.py` |
| Divergência | `src/detection/divergence.py` |
| Volume | `src/detection/volume_confirm.py` |
| Fibonacci | `src/detection/fibonacci_zone.py` |
| Padrão | `src/detection/reversal_pattern.py` |
| Scanner | `src/detection/divap_scanner.py` |
