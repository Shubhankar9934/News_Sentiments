# Signal Engine (Frontend Desk Derivation)

**File:** `frontend/src/lib/deriveTradeDecision.ts`

This is the **trading desk signal engine** for the UI. It is **not** persisted and **not** computed on the backend.

## Outputs

| Output | Type | Notes |
|--------|------|-------|
| `signal` | string | From Claude bias or overall label |
| `signalConfidencePct` | 0–99 | Claude confidence or FinBERT fallback |
| `newsStrength` | WEAK/MODERATE/STRONG | Article count + avg top impact |
| `riskLevel` | LOW/MEDIUM/HIGH | Mixed + vol regime |
| `tradeQuality` | A+ … NO TRADE | Heuristic grade |
| `noTrade` | boolean | Mixed + low conf |
| `alignment.*` | YES/WEAK/NO/UNKNOWN | Price, volume, momentum |
| `contradictory.bullets` | string[] | Rule-based flags |

## Trade quality thresholds

```
NO TRADE if noTrade
A      if conf >= 85 && no contradictions
A-     if conf >= 78 && newsStrength STRONG && no contradictions
B+     if conf >= 70
C      if conf < 45
B      default
```

## NO TRADE

```
mixed sentiment label && confidence < 48 && newsStrength !== STRONG
```

## Alignment thresholds

| Check | YES | WEAK | NO |
|-------|-----|------|-----|
| Volume vs avg | ≥ 1.15 | ≥ 0.9 | < 0.9 |
| Price vs bias | session + abnormal agree | \|session\| < 0.15% | conflict |
| Momentum | high vol + STRONG news | partial | — |

**Rating:** HIGH RISK — displayed as institutional metrics without backtest.
