# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cheapest+cleanest region: europe-north1

_Figures are June-2026 as-of snapshots; re-baseline before acting._

## Reasoning token budget

| Traffic | Requests | Tokens | Actual optimized cost | Energy | Standard-route cost at equal token volume | Energy at equal token volume |
|---|---:|---:|---:|---:|---:|---:|
| is_reasoning=0 | 2,199 | 6,291,871 | $7.09 | 1,887.56 Wh | $0.23 | 372.35 Wh |
| is_reasoning=1 | 201 | 1,241,156 | $1.40 | 29,787.74 Wh | $0.20 | 29,787.74 Wh |

Equal-volume comparison uses 1,241,156 tokens per cohort. Reasoning costs 0.86x and uses 80.0x the energy of non-reasoning traffic at that volume.

**Routing proposal:** enable reasoning only when the confidence score is below 0.70; route higher-confidence requests through the standard path. This is a starting threshold and should be tuned against quality and latency targets.
