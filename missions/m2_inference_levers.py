"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0
    reasoning = {
        0: {"requests": 0, "tokens": 0, "cost": 0.0, "wh": 0.0},
        1: {"requests": 0, "tokens": 0, "cost": 0.0, "wh": 0.0},
    }
    comparison_cost_per_flag = {0: 0.0, 1: 0.0}
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = 1 if int(num(r.get("is_reasoning", 0))) else 0
        tokens = inp + out
        total_tokens += tokens
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        request_opt_cost = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        opt_cost += request_opt_cost
        # Counterfactual comparison: price both cohorts on the same standard
        # (non-reasoning) route so model-tier mix does not masquerade as a
        # reasoning surcharge.
        comparison_cost_per_flag[is_reasoning] += pricing.request_cost(
            inp, out, *MODEL_PRICES["small"], cached_in=cached, batch=is_batch
        )
        group = reasoning[is_reasoning]
        group["requests"] += 1
        group["tokens"] += tokens
        group["cost"] += request_opt_cost
        group["wh"] += sustainability.wh_per_query(tokens, is_reasoning=bool(is_reasoning))

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    # Normalize both cohorts to the smaller cohort's token count for a direct,
    # equal-volume comparison (while also returning their observed totals).
    comparable_tokens = min(reasoning[0]["tokens"], reasoning[1]["tokens"])
    for flag, group in reasoning.items():
        scale = comparable_tokens / group["tokens"] if group["tokens"] else 0.0
        group["comparable_tokens"] = comparable_tokens
        group["cost_at_comparable_tokens"] = comparison_cost_per_flag[flag] * scale
        group["wh_at_comparable_tokens"] = group["wh"] * scale

    reasoning_comparison = {
        "comparable_tokens": comparable_tokens,
        "non_reasoning": reasoning[0],
        "reasoning": reasoning[1],
        "cost_ratio_per_equal_tokens": (
            reasoning[1]["cost_at_comparable_tokens"] / reasoning[0]["cost_at_comparable_tokens"]
            if reasoning[0]["cost_at_comparable_tokens"] else 0.0
        ),
        "wh_ratio_per_equal_tokens": (
            reasoning[1]["wh_at_comparable_tokens"] / reasoning[0]["wh_at_comparable_tokens"]
            if reasoning[0]["wh_at_comparable_tokens"] else 0.0
        ),
        "confidence_threshold": 0.70,
    }

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print("reasoning traffic (optimized cost / energy):")
        for flag, label in ((0, "non-reasoning"), (1, "reasoning")):
            group = reasoning[flag]
            print(f"  {label:14} {group['requests']:4} requests, {group['tokens']:,} tokens, actual optimized ${group['cost']:,.2f}, {group['wh']:,.2f} Wh")
            print(f"  equal-volume   standard-route cost ${group['cost_at_comparable_tokens']:,.2f} / {group['wh_at_comparable_tokens']:,.2f} Wh for {comparable_tokens:,} tokens")
        print(f"  equal-token ratio (reasoning/non): ${reasoning_comparison['cost_ratio_per_equal_tokens']:.2f}x, {reasoning_comparison['wh_ratio_per_equal_tokens']:.1f}x energy")
        print("  policy: enable reasoning only when confidence < 0.70; otherwise use the standard route")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "reasoning_comparison": reasoning_comparison,
    }


if __name__ == "__main__":
    run()
