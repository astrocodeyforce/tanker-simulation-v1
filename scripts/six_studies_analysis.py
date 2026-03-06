#!/usr/bin/env python3
"""
six_studies_analysis.py — Analyze results from all 6 simulation studies.

Reads output CSVs from data/runs/ matching study prefixes s1_ through s6_.
Produces a comprehensive report.
"""

import csv
import os
import glob
import json
import sys

RUNS_DIR = "/opt/sim-lab/truck-tanker-sim-env/data/runs"
TIME_LIMIT_S = 5400  # 90 min = 1.5 hours
TIME_LIMIT_MIN = 90.0
INITIAL_VOL_GAL = 6500.0
COMPLETION_PCT = 0.99  # 99%


def find_run(scenario_name):
    """Find the latest run dir for a scenario name."""
    pattern = os.path.join(RUNS_DIR, f"*_{scenario_name}")
    dirs = sorted(glob.glob(pattern))
    return dirs[-1] if dirs else None


def parse_csv(csv_path):
    """Parse simulation output CSV. Returns dict of arrays.
    Optimized: samples every Nth row for large files, but keeps
    first/last rows and rows near completion threshold."""
    data = {"time_s": [], "Q_L_gpm": [], "V_liquid_gal": [],
            "V_transferred_gal": [], "P_tank_psig": []}
    
    # Count lines to decide sampling
    with open(csv_path) as f:
        line_count = sum(1 for _ in f)
    
    # Sample rate: keep every Nth row (always keep first/last 100 rows)
    if line_count > 10000:
        sample_every = max(1, line_count // 5000)  # ~5000 data points max
    else:
        sample_every = 1
    
    row_idx = 0
    completed = False
    with open(csv_path) as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            row_idx += 1
            if len(row) < 10:
                continue
            
            # Always keep first 100 rows, last section, and sampled rows
            if row_idx > 100 and sample_every > 1 and row_idx % sample_every != 0:
                # But always keep rows near completion
                vt = float(row[9])
                init_approx = float(row[7]) + vt if row_idx < 5 else data["V_liquid_gal"][0] + data["V_transferred_gal"][0] if data["V_liquid_gal"] else 6500
                if not completed and vt < init_approx * 0.95:
                    continue
            
            t = float(row[0])
            data["time_s"].append(t)
            data["P_tank_psig"].append(float(row[1]))
            data["Q_L_gpm"].append(float(row[5]))
            data["V_liquid_gal"].append(float(row[7]))
            data["V_transferred_gal"].append(float(row[9]))
            
            # Mark when we've passed 99% completion
            if not completed and data["V_transferred_gal"][-1] > 0:
                init = data["V_liquid_gal"][0] + data["V_transferred_gal"][0] if len(data["V_liquid_gal"]) > 0 else 6500
                if data["V_transferred_gal"][-1] >= init * 0.99:
                    completed = True
    
    return data


def completion_time_min(data, threshold_gal=None):
    """Time in minutes to transfer threshold_gal gallons. Returns None if not reached."""
    if threshold_gal is None:
        # Infer from initial volume
        init_vol = data["V_liquid_gal"][0] if data["V_liquid_gal"] else INITIAL_VOL_GAL
        threshold_gal = init_vol * COMPLETION_PCT
    
    times = data["time_s"]
    vt = data["V_transferred_gal"]
    for i in range(len(vt)):
        if vt[i] >= threshold_gal:
            if i > 0 and vt[i] != vt[i-1]:
                frac = (threshold_gal - vt[i-1]) / (vt[i] - vt[i-1])
                t = times[i-1] + frac * (times[i] - times[i-1])
            else:
                t = times[i]
            return t / 60.0
    return None


def avg_gpm(data, end_time_s=None):
    """Time-weighted average GPM."""
    times = data["time_s"]
    q = data["Q_L_gpm"]
    if len(times) < 2:
        return 0
    total_flow = 0
    total_time = 0
    for i in range(1, len(times)):
        if end_time_s and times[i] > end_time_s:
            dt = end_time_s - times[i-1]
            if dt > 0:
                total_flow += (q[i-1] + q[i]) / 2 * dt
                total_time += dt
            break
        dt = times[i] - times[i-1]
        total_flow += (q[i-1] + q[i]) / 2 * dt
        total_time += dt
    return total_flow / total_time if total_time > 0 else 0


def analyze_scenario(scenario_name):
    """Full analysis of a single simulation run. Returns dict or None."""
    run_dir = find_run(scenario_name)
    if not run_dir:
        return None
    csv_path = os.path.join(run_dir, "outputs.csv")
    if not os.path.exists(csv_path):
        return None
    
    data = parse_csv(csv_path)
    if not data["time_s"]:
        return None
    
    init_vol = data["V_liquid_gal"][0]
    threshold = init_vol * COMPLETION_PCT
    
    comp_min = completion_time_min(data, threshold)
    end_s = comp_min * 60 if comp_min else data["time_s"][-1]
    
    return {
        "scenario": scenario_name,
        "initial_vol_gal": init_vol,
        "comp_time_min": comp_min,
        "avg_gpm": avg_gpm(data, end_s),
        "peak_gpm": max(data["Q_L_gpm"]) if data["Q_L_gpm"] else 0,
        "peak_psig": max(data["P_tank_psig"]) if data["P_tank_psig"] else 0,
        "final_transferred_gal": data["V_transferred_gal"][-1] if data["V_transferred_gal"] else 0,
        "passes_90": comp_min is not None and comp_min <= TIME_LIMIT_MIN,
    }


def parse_manifest():
    """Parse studies manifest. Returns list of (study, scenario, yaml, meta_dict)."""
    manifest = os.path.join(os.path.dirname(RUNS_DIR), "..", "config", "studies", "studies_manifest.txt")
    manifest = "/opt/sim-lab/truck-tanker-sim-env/config/studies/studies_manifest.txt"
    entries = []
    with open(manifest) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            study, scenario, yaml_file = parts[0], parts[1], parts[2]
            meta = {}
            if len(parts) > 3:
                for kv in parts[3].split(","):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        try:
                            v = float(v)
                            if v == int(v):
                                v = int(v)
                        except ValueError:
                            pass
                        meta[k] = v
            entries.append((study, scenario, yaml_file, meta))
    return entries


# =============================================================================
# STUDY REPORTERS
# =============================================================================

def report_study1(entries, results):
    """Compressor Sizing — SCFM sweep for failing products."""
    print("\n" + "=" * 100)
    print("  STUDY 1: COMPRESSOR SIZING — What SCFM saves the day?")
    print("  Sweep: 19, 25, 30, 40, 50, 75, 100 SCFM × plant air / PTO compressor")
    print("=" * 100)
    
    # Group by product
    products = {}
    for study, scenario, _, meta in entries:
        if study != "study1":
            continue
        r = results.get(scenario)
        if not r:
            continue
        prod = meta.get("product", "?")
        if prod not in products:
            products[prod] = []
        products[prod].append({**r, **meta})
    
    for prod, runs in sorted(products.items()):
        cP = runs[0].get("cP", "?")
        print(f"\n  ─── {prod} ({cP} cP) ───")
        print(f"  {'SCFM':>6} {'Type':<8} {'Time(min)':>10} {'Avg GPM':>9} {'Peak GPM':>9} {'Peak PSI':>9} {'Pass?':>6}")
        print(f"  {'─'*6} {'─'*8} {'─'*10} {'─'*9} {'─'*9} {'─'*9} {'─'*6}")
        
        for r in sorted(runs, key=lambda x: (x.get("comp_type", ""), x.get("scfm", 0))):
            comp = f"{r['comp_time_min']:.1f}" if r.get("comp_time_min") else "N/A"
            mark = "✅" if r.get("passes_90") else "❌"
            print(f"  {r.get('scfm',''):>6} {r.get('comp_type',''):<8} {comp:>10} {r['avg_gpm']:>9.1f} {r['peak_gpm']:>9.1f} {r['peak_psig']:>9.1f} {mark:>6}")
        
        # Find minimum SCFM that passes for each comp type
        for ct in ["plant", "pto"]:
            ct_runs = [r for r in runs if r.get("comp_type") == ct and r.get("passes_90")]
            if ct_runs:
                min_scfm = min(r.get("scfm", 999) for r in ct_runs)
                print(f"  → Min SCFM for PASS ({ct}): {min_scfm} SCFM")
            else:
                print(f"  → No SCFM passes 90 min ({ct})")


def report_study2(entries, results):
    """Hose Upgrade — 3" vs 4"."""
    print("\n" + "=" * 100)
    print("  STUDY 2: HOSE UPGRADE — 3\" vs 4\" (with matching valve)")
    print("=" * 100)
    
    # Build comparison pairs
    pairs = {}  # product -> {3: result, 4: result}
    for study, scenario, _, meta in entries:
        if study != "study2":
            continue
        r = results.get(scenario)
        if not r:
            continue
        prod = meta.get("product", "?")
        hose = meta.get("hose_in", 3)
        if prod not in pairs:
            pairs[prod] = {}
        pairs[prod][hose] = {**r, **meta}
    
    print(f"\n  {'Product':<25} │ {'3\" Time':>8} {'3\" GPM':>7} │ {'4\" Time':>8} {'4\" GPM':>7} │ {'Saved':>7} {'Faster':>7}")
    print(f"  {'─'*25} ┼ {'─'*8} {'─'*7} ┼ {'─'*8} {'─'*7} ┼ {'─'*7} {'─'*7}")
    
    savings = []
    for prod in sorted(pairs.keys(), key=lambda p: pairs[p].get(3, {}).get("cP", 0)):
        r3 = pairs[prod].get(3.0) or pairs[prod].get(3)
        r4 = pairs[prod].get(4.0) or pairs[prod].get(4)
        
        if not r3 or not r4:
            continue
        
        t3 = r3.get("comp_time_min")
        t4 = r4.get("comp_time_min")
        g3 = r3.get("avg_gpm", 0)
        g4 = r4.get("avg_gpm", 0)
        
        t3s = f"{t3:.1f}" if t3 else "N/A"
        t4s = f"{t4:.1f}" if t4 else "N/A"
        
        if t3 and t4:
            saved = t3 - t4
            pct = (saved / t3) * 100
            savings.append((prod, saved, pct, r3.get("cP", 0)))
            saved_s = f"{saved:+.1f}m"
            pct_s = f"{pct:+.1f}%"
        else:
            saved_s = "—"
            pct_s = "—"
        
        print(f"  {prod:<25} │ {t3s:>8} {g3:>7.1f} │ {t4s:>8} {g4:>7.1f} │ {saved_s:>7} {pct_s:>7}")
    
    if savings:
        avg_saved = sum(s for _, s, _, _ in savings) / len(savings)
        avg_pct = sum(p for _, _, p, _ in savings) / len(savings)
        print(f"\n  Average time saved with 4\" upgrade: {avg_saved:.1f} min ({avg_pct:.1f}%)")
        
        # Who benefits most
        best = max(savings, key=lambda x: x[1])
        print(f"  Biggest benefit: {best[0]} saves {best[1]:.1f} min ({best[2]:.1f}%)")


def report_study3(entries, results):
    """Break-Even Viscosity."""
    print("\n" + "=" * 100)
    print("  STUDY 3: BREAK-EVEN VISCOSITY — Exact cP cutoff at current equipment")
    print("  (19 SCFM, 3\" valve/hose, 6500 gal, SG=1.1)")
    print("=" * 100)
    
    rows = []
    for study, scenario, _, meta in entries:
        if study != "study3":
            continue
        r = results.get(scenario)
        if not r:
            continue
        rows.append({**r, **meta})
    
    rows.sort(key=lambda x: x.get("cP", 0))
    
    print(f"\n  {'Viscosity':>10} {'Time(min)':>10} {'Avg GPM':>9} {'Pass 90min?':>12}")
    print(f"  {'─'*10} {'─'*10} {'─'*9} {'─'*12}")
    
    last_pass = None
    first_fail = None
    for r in rows:
        comp = f"{r['comp_time_min']:.1f}" if r.get("comp_time_min") else "N/A"
        mark = "✅ PASS" if r.get("passes_90") else "❌ FAIL"
        print(f"  {r.get('cP',0):>8} cP {comp:>10} {r['avg_gpm']:>9.1f} {mark:>12}")
        if r.get("passes_90"):
            last_pass = r
        elif first_fail is None:
            first_fail = r
    
    if last_pass and first_fail:
        lp = last_pass.get("cP", 0)
        ff = first_fail.get("cP", 0)
        # Linear interpolation for the exact cutoff
        lt = last_pass.get("comp_time_min", 0)
        ft = first_fail.get("comp_time_min") or 999
        if ft != lt:
            cutoff = lp + (ff - lp) * (90 - lt) / (ft - lt)
        else:
            cutoff = (lp + ff) / 2
        print(f"\n  ★ BREAK-EVEN VISCOSITY: ~{cutoff:.0f} cP")
        print(f"    Last PASS: {lp} cP @ {lt:.1f} min")
        print(f"    First FAIL: {ff} cP @ {ft:.1f} min" if ft < 999 else f"    First FAIL: {ff} cP (did not complete)")


def report_study4(entries, results):
    """Equipment Combo Optimizer."""
    print("\n" + "=" * 100)
    print("  STUDY 4: EQUIPMENT COMBO OPTIMIZER — SCFM × hose × valve for failing products")
    print("=" * 100)
    
    products = {}
    for study, scenario, _, meta in entries:
        if study != "study4":
            continue
        r = results.get(scenario)
        if not r:
            continue
        prod = meta.get("product", "?")
        if prod not in products:
            products[prod] = []
        products[prod].append({**r, **meta})
    
    for prod, runs in sorted(products.items()):
        cP = runs[0].get("cP", "?")
        print(f"\n  ─── {prod} ({cP} cP) ───")
        print(f"  {'SCFM':>6} {'Hose':>5} {'Valve':>6} {'Time(min)':>10} {'Avg GPM':>9} {'Pass?':>6}")
        print(f"  {'─'*6} {'─'*5} {'─'*6} {'─'*10} {'─'*9} {'─'*6}")
        
        for r in sorted(runs, key=lambda x: (x.get("scfm",0), x.get("hose_in",0), x.get("valve_in",0))):
            comp = f"{r['comp_time_min']:.1f}" if r.get("comp_time_min") else "N/A"
            mark = "✅" if r.get("passes_90") else "❌"
            h = f'{r.get("hose_in",3):.0f}"'
            v = f'{r.get("valve_in",3):.0f}"'
            print(f"  {r.get('scfm',''):>6} {h:>5} {v:>6} {comp:>10} {r['avg_gpm']:>9.1f} {mark:>6}")
        
        # Best passing combo
        passing = [r for r in runs if r.get("passes_90")]
        if passing:
            cheapest = min(passing, key=lambda r: r.get("scfm", 999))
            print(f"  → Cheapest passing combo: {cheapest.get('scfm')} SCFM, {cheapest.get('hose_in')}\" hose, {cheapest.get('valve_in')}\" valve → {cheapest['comp_time_min']:.1f} min")
        else:
            print(f"  → No combo passes 90 min within tested range")


def report_study5(entries, results):
    """Partial Load Study."""
    print("\n" + "=" * 100)
    print("  STUDY 5: PARTIAL LOADS — Does a smaller load make the cutoff?")
    print("=" * 100)
    
    products = {}
    for study, scenario, _, meta in entries:
        if study != "study5":
            continue
        r = results.get(scenario)
        if not r:
            continue
        prod = meta.get("product", "?")
        if prod not in products:
            products[prod] = []
        products[prod].append({**r, **meta})
    
    print(f"\n  {'Product':<25} {'cP':>7} │", end="")
    vols = [2000, 3000, 4000, 5000, 6500]
    for v in vols:
        print(f" {v:>6}gal", end="")
    print()
    print(f"  {'─'*25} {'─'*7} ┼" + "─" * (9 * len(vols)))
    
    for prod in sorted(products.keys(), key=lambda p: products[p][0].get("cP", 0)):
        runs = products[prod]
        cP = runs[0].get("cP", "?")
        print(f"  {prod:<25} {cP:>7} │", end="")
        runs_by_vol = {r.get("volume_gal"): r for r in runs}
        for v in vols:
            r = runs_by_vol.get(v)
            if r and r.get("comp_time_min"):
                t = r["comp_time_min"]
                mark = "✓" if t <= 90 else "✗"
                print(f" {t:>5.1f}{mark} ", end="")
            else:
                print(f"   N/A  ", end="")
        print()
    
    print(f"\n  Values = completion time in minutes. ✓ = ≤90min, ✗ = >90min")


def report_study6(entries, results):
    """Elevation + Back-pressure."""
    print("\n" + "=" * 100)
    print("  STUDY 6: SITE CONDITIONS — Elevation & Back-pressure Impact")
    print("=" * 100)
    
    products = {}
    for study, scenario, _, meta in entries:
        if study != "study6":
            continue
        r = results.get(scenario)
        if not r:
            continue
        prod = meta.get("product", "?")
        if prod not in products:
            products[prod] = []
        products[prod].append({**r, **meta})
    
    for prod in sorted(products.keys(), key=lambda p: products[p][0].get("cP", 0)):
        runs = products[prod]
        cP = runs[0].get("cP", "?")
        print(f"\n  ─── {prod} ({cP} cP) ───")
        
        # Grid: elevation × backpressure
        elevs = sorted(set(r.get("elevation_ft", 0) for r in runs))
        bps = sorted(set(r.get("backpressure_psig", 0) for r in runs))
        
        # Header
        print(f"  {'Elev↓ \\ BP→':>14}", end="")
        for bp in bps:
            print(f" {bp:>6}psi", end="")
        print()
        print(f"  {'─'*14}" + "─" * (9 * len(bps)))
        
        lookup = {}
        for r in runs:
            key = (r.get("elevation_ft", 0), r.get("backpressure_psig", 0))
            lookup[key] = r
        
        for elev in elevs:
            print(f"  {elev:>10} ft  ", end="")
            for bp in bps:
                r = lookup.get((elev, bp))
                if r and r.get("comp_time_min"):
                    t = r["comp_time_min"]
                    mark = "✓" if t <= 90 else "✗"
                    print(f" {t:>5.1f}{mark} ", end="")
                else:
                    print(f"   N/A  ", end="")
            print()
        print(f"  (times in minutes, ✓=pass, ✗=fail)")


# =============================================================================
# MAIN
# =============================================================================
def main():
    entries = parse_manifest()
    
    # Gather results
    print("Analyzing simulation results...")
    results = {}
    missing = 0
    for study, scenario, _, meta in entries:
        r = analyze_scenario(scenario)
        if r:
            results[scenario] = r
        else:
            missing += 1
    
    print(f"  Found: {len(results)} / {len(entries)} scenario results ({missing} missing)")
    
    # Filter to studies that have results
    studies_present = set()
    for study, scenario, _, _ in entries:
        if scenario in results:
            studies_present.add(study)
    
    # Print header
    print("\n" + "█" * 100)
    print("  BULL & BEAR TRUCKING — SIX SIMULATION STUDIES REPORT")
    print("  Base Parameters: 6,500 gal T5183 tanker | 19 SCFM | 3\" valve/hose 20ft")
    print("  Date: " + __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("█" * 100)
    
    if "study1" in studies_present:
        report_study1(entries, results)
    if "study2" in studies_present:
        report_study2(entries, results)
    if "study3" in studies_present:
        report_study3(entries, results)
    if "study4" in studies_present:
        report_study4(entries, results)
    if "study5" in studies_present:
        report_study5(entries, results)
    if "study6" in studies_present:
        report_study6(entries, results)
    
    # Final summary
    print("\n" + "█" * 100)
    print("  EXECUTIVE SUMMARY")
    print("█" * 100)
    
    # Count passes by study
    for sid in ["study1", "study2", "study3", "study4", "study5", "study6"]:
        study_entries = [(s, sc, y, m) for s, sc, y, m in entries if s == sid and sc in results]
        if not study_entries:
            continue
        total = len(study_entries)
        passing = sum(1 for _, sc, _, _ in study_entries if results[sc].get("passes_90"))
        print(f"  {sid}: {total} sims, {passing} pass 90-min ({passing/total*100:.0f}%)")
    
    total_sims = len(results)
    total_passing = sum(1 for r in results.values() if r.get("passes_90"))
    print(f"\n  TOTAL: {total_sims} simulations, {total_passing} pass 90-min ({total_passing/total_sims*100:.0f}%)")
    print()


if __name__ == "__main__":
    main()
