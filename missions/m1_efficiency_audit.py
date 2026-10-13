"""M1 — Efficiency Audit: MFU/MBU, the GPU-Util lie, and idle waste (deck §5).

Run: python missions/m1_efficiency_audit.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from collections import defaultdict
from missions._common import load_csv, num, catalog_by_type
from finops import metrics


def run(verbose: bool = True) -> dict:
    tel = load_csv("gpu_telemetry.csv")
    cat = catalog_by_type()

    # per-row MFU/MBU, then aggregate per GPU
    agg = defaultdict(lambda: {"util": [], "mfu": [], "mbu": [], "type": None, "idle_hours": 0})
    for r in tel:
        gtype = r["gpu_type"]
        peak_fp16 = num(cat[gtype]["peak_tflops_fp16"])
        peak_bw = num(cat[gtype]["peak_bw_tbs"])
        mfu = metrics.compute_mfu(num(r["achieved_tflops"]), peak_fp16)
        mbu = metrics.compute_mbu(num(r["achieved_bw_tbs"]), peak_bw)
        a = agg[r["gpu_id"]]
        a["type"] = gtype
        a["util"].append(num(r["gpu_util_pct"]))
        a["mfu"].append(mfu)
        a["mbu"].append(mbu)
        if num(r["gpu_util_pct"]) < 10:  # effectively idle this interval (1h)
            a["idle_hours"] += 1

    summary = []
    for gid, a in agg.items():
        summary.append({
            "gpu_id": gid, "gpu_type": a["type"],
            "gpu_util_pct": round(sum(a["util"]) / len(a["util"]), 1),
            "mfu": round(sum(a["mfu"]) / len(a["mfu"]), 3),
            "mbu": round(sum(a["mbu"]) / len(a["mbu"]), 3),
            "idle_hours": a["idle_hours"],
        })

    # Compare memory-bound GPUs against cheaper alternatives that can keep
    # the same workload MBU target without reducing VRAM or peak bandwidth.
    gpu_economics = {}
    for gtype, row in cat.items():
        hbm_gb = num(row.get("hbm_gb", 0))
        price = num(row.get("on_demand_hr", 0))
        gpu_economics[gtype] = {
            "hbm_gb": hbm_gb,
            "peak_bw_tbs": num(row.get("peak_bw_tbs", 0)),
            "on_demand_hr": price,
            "usd_per_gb_vram_hr": price / hbm_gb if hbm_gb > 0 else 0.0,
        }

    rightsizing = []
    for s in summary:
        if s["mbu"] >= 0.60:
            continue
        source = gpu_economics[s["gpu_type"]]
        alternatives = [
            (gtype, econ) for gtype, econ in gpu_economics.items()
            if gtype != s["gpu_type"]
            and econ["hbm_gb"] >= source["hbm_gb"]
            and econ["peak_bw_tbs"] >= source["peak_bw_tbs"]
            and econ["on_demand_hr"] < source["on_demand_hr"]
        ]
        if alternatives:
            target_type, target = min(
                alternatives,
                key=lambda item: item[1]["on_demand_hr"],
            )
            rightsizing.append({
                "gpu_id": s["gpu_id"],
                "gpu_type": s["gpu_type"],
                "mbu_target": s["mbu"],
                "suggested_gpu": target_type,
                "source_usd_per_gb_vram_hr": round(source["usd_per_gb_vram_hr"], 4),
                "suggested_usd_per_gb_vram_hr": round(target["usd_per_gb_vram_hr"], 4),
            })

    lies = metrics.flag_util_lies(summary)
    idle_waste = 0.0
    for s in summary:
        on_demand = num(catalog_by_type()[s["gpu_type"]]["on_demand_hr"])
        idle_waste += metrics.idle_waste_usd(s["idle_hours"], on_demand)

    if verbose:
        print("== M1 Efficiency Audit ==")
        print(f"{'GPU':14}{'type':7}{'util%':>7}{'MFU':>7}{'MBU':>7}{'idle_h':>8}")
        for s in sorted(summary, key=lambda x: x["mfu"]):
            print(f"{s['gpu_id']:14}{s['gpu_type']:7}{s['gpu_util_pct']:>7}{s['mfu']:>7}{s['mbu']:>7}{s['idle_hours']:>8}")
        print(f"\nGPU-Util LIES (util>=90% but MFU<30%): {[l['gpu_id'] for l in lies]}")
        print(f"Idle waste (1 day): ${idle_waste:,.2f}  ->  ${idle_waste*30:,.0f}/month")
        print("$/GB-VRAM-hour by GPU:")
        for gtype, econ in sorted(gpu_economics.items(), key=lambda item: item[1]["usd_per_gb_vram_hr"]):
            print(f"  {gtype:8} ${econ['usd_per_gb_vram_hr']:.4f}  peak BW {econ['peak_bw_tbs']:.2f} TB/s")
        print("Memory-bound right-sizing suggestions (MBU < 0.60; matching VRAM/BW):")
        for suggestion in rightsizing:
            print(
                f"  {suggestion['gpu_id']} ({suggestion['gpu_type']}, MBU target {suggestion['mbu_target']:.3f})"
                f" -> {suggestion['suggested_gpu']}"
                f" (${suggestion['source_usd_per_gb_vram_hr']:.4f} ->"
                f" ${suggestion['suggested_usd_per_gb_vram_hr']:.4f}/GB-VRAM-hour)"
            )

    return {
        "summary": summary,
        "lies": lies,
        "idle_waste_daily": round(idle_waste, 2),
        "gpu_economics": gpu_economics,
        "rightsizing": rightsizing,
    }


if __name__ == "__main__":
    run()
