# Partial Take Profits (25% · 50% · 100%)

## Goal

Scale out of open positions in three equal parts at interpolated price levels
(25%, 50%, 100% of the move to the final DIVAP take-profit).

## Behavior

- **TP1 @ 25%** → close ~33.3% of position; move stop to breakeven
- **TP2 @ 50%** → close ~33.3%
- **TP3 @ 100%** → close remainder; trade closed

- RR gate unchanged (uses final TP at 100%)
- Telegram: partial message on TP1/TP2; full close message on TP3
- Default profile: `divap_ativo`; other profiles keep single TP

## Config (YAML)

```yaml
exit:
  partial_take_profits:
    - { distance_pct: 25 }
    - { distance_pct: 50 }
    - { distance_pct: 100 }
  move_stop_to_breakeven_after: 1
```
