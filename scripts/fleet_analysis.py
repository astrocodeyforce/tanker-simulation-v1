#!/usr/bin/env python3
"""
Fleet Batch Simulation Results Analysis
Bull & Bear Trucking - Top 20 Products
6500 gal tanker, 19 SCFM airflow, 1.5-hour (90 min) cutoff
"""

import csv
import os
import glob
import json

RUNS_DIR = "/opt/sim-lab/truck-tanker-sim-env/data/runs"
TIME_LIMIT_MIN = 90.0  # 1.5 hours
INITIAL_VOL_GAL = 6500.0
COMPLETION_THRESHOLD = 0.99  # 99% transferred = "done"

# Product metadata: name -> (viscosity_cP, SG, loads)
PRODUCTS = {
    "fleet_ethylene_glycol":       ("Ethylene Glycol",       16.1,  1.113, 128),
    "fleet_resin_solution":        ("Resin Solution",       500.0,  1.05,  106),
    "fleet_sodium_silicate":       ("Sodium Silicate",      180.0,  1.39,   96),
    "fleet_biomass":               ("Biomass",               50.0,  1.05,   70),
    "fleet_diethylene_glycol":     ("Diethylene Glycol",     30.2,  1.118,  60),
    "fleet_doss_70_pg":            ("DOSS 70 PG",           200.0,  1.08,   56),
    "fleet_nipol_1411_latex":      ("NIPOL 1411 LATEX",     200.0,  1.0,    52),
    "fleet_smartcide_1984a":       ("Smartcide 1984A",        5.0,  1.02,   44),
    "fleet_transformer_oil_type_ii": ("Transformer Oil II",  11.0,  0.88,   43),
    "fleet_used_motor_oil":        ("Used Motor Oil",        20.0,  0.88,   40),
    "fleet_ocd":                   ("OCD",                    0.6,  1.05,   39),
    "fleet_triethylene_glycol":    ("Triethylene Glycol",    37.3,  1.125,  35),
    "fleet_propylene_glycol":      ("Propylene Glycol",      42.0,  1.036,  35),
    "fleet_tall_oil_rosin":        ("Tall Oil Rosin",      5000.0,  1.07,   31),
    "fleet_vivatec_500":           ("VIVATEC 500",          100.0,  0.99,   27),
    "fleet_wax_additive_c24_28":   ("Wax Additive C24-28",   5.0,  0.80,   26),
    "fleet_kaolin_clay":           ("Kaolin Clay",          300.0,  1.15,   25),
    "fleet_crude_glycerin":        ("CRUDE GLYCERIN",       934.0,  1.261,  24),
    "fleet_tea_99":                ("TEA 99",               590.0,  1.124,  24),
    "fleet_perchloroethylene":     ("Perchloroethylene",   9900.0,  1.622,  22),
}

def find_latest_run(product_key):
    """Find the latest run directory for a product."""
    pattern = os.path.join(RUNS_DIR, f"*_{product_key}")
    dirs = sorted(glob.glob(pattern))
    if dirs:
        return dirs[-1]
    return None

def analyze_csv(csv_path):
    """Parse output CSV and extract key metrics."""
    times = []
    v_liquid_gal = []
    v_transferred_gal = []
    q_gpm = []
    
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) < 10:
                continue
            t = float(row[0])
            ql = float(row[5])   # Q_L_gpm
            vl = float(row[7])   # V_liquid_gal
            vt = float(row[9])   # V_transferred_gal
            times.append(t)
            q_gpm.append(ql)
            v_liquid_gal.append(vl)
            v_transferred_gal.append(vt)
    
    return times, q_gpm, v_liquid_gal, v_transferred_gal

def find_completion_time(times, v_transferred_gal, threshold_gal):
    """Find time when transferred volume reaches threshold."""
    for i, vt in enumerate(v_transferred_gal):
        if vt >= threshold_gal:
            # Linear interpolation
            if i > 0:
                prev_vt = v_transferred_gal[i-1]
                prev_t = times[i-1]
                frac = (threshold_gal - prev_vt) / (vt - prev_vt) if vt != prev_vt else 0
                return prev_t + frac * (times[i] - prev_t)
            return times[i]
    return None  # Never completed

def compute_avg_gpm(times, q_gpm, end_time_s=None):
    """Compute time-weighted average GPM up to end_time."""
    if len(times) < 2:
        return 0
    total_flow = 0
    total_time = 0
    for i in range(1, len(times)):
        if end_time_s and times[i] > end_time_s:
            # Partial last interval
            dt = end_time_s - times[i-1]
            if dt > 0:
                avg_q = (q_gpm[i-1] + q_gpm[i]) / 2
                total_flow += avg_q * dt
                total_time += dt
            break
        dt = times[i] - times[i-1]
        avg_q = (q_gpm[i-1] + q_gpm[i]) / 2
        total_flow += avg_q * dt
        total_time += dt
    return total_flow / total_time if total_time > 0 else 0

def gpm_at_90min(times, q_gpm):
    """Get GPM at the 90-minute mark (or nearest)."""
    target = 90 * 60  # 5400 seconds
    for i in range(len(times)):
        if times[i] >= target:
            return q_gpm[i]
    return q_gpm[-1] if q_gpm else 0

def vol_at_90min(times, v_transferred_gal):
    """Get volume transferred at 90 minutes."""
    target = 90 * 60
    for i in range(len(times)):
        if times[i] >= target:
            if i > 0:
                frac = (target - times[i-1]) / (times[i] - times[i-1])
                return v_transferred_gal[i-1] + frac * (v_transferred_gal[i] - v_transferred_gal[i-1])
            return v_transferred_gal[i]
    return v_transferred_gal[-1] if v_transferred_gal else 0

def main():
    threshold_gal = INITIAL_VOL_GAL * COMPLETION_THRESHOLD  # 6435 gal
    
    results = []
    
    for product_key, (name, visc, sg, loads) in PRODUCTS.items():
        run_dir = find_latest_run(product_key)
        if not run_dir:
            print(f"  WARNING: No run found for {product_key}")
            results.append({
                'name': name, 'viscosity': visc, 'sg': sg, 'loads': loads,
                'completion_time_min': None, 'avg_gpm': 0, 'passes': False,
                'vol_at_90': 0, 'pct_at_90': 0,
            })
            continue
        
        csv_path = os.path.join(run_dir, "outputs.csv")
        if not os.path.exists(csv_path):
            print(f"  WARNING: No outputs.csv in {run_dir}")
            continue
        
        times, q_gpm_data, v_liquid, v_transferred = analyze_csv(csv_path)
        
        comp_time_s = find_completion_time(times, v_transferred, threshold_gal)
        comp_time_min = comp_time_s / 60 if comp_time_s else None
        
        # Average GPM over full transfer (or up to sim end)
        end_s = comp_time_s if comp_time_s else times[-1]
        avg_gpm = compute_avg_gpm(times, q_gpm_data, end_s)
        
        # Simple GPM = volume / time
        if comp_time_min and comp_time_min > 0:
            simple_gpm = threshold_gal / comp_time_min
        else:
            # Didn't complete - use total transferred / total time
            simple_gpm = v_transferred[-1] / (times[-1] / 60) if times[-1] > 0 else 0
        
        # Volume transferred at 90 minutes
        v90 = vol_at_90min(times, v_transferred)
        pct90 = (v90 / INITIAL_VOL_GAL) * 100
        
        # Peak GPM (usually at start)
        peak_gpm = max(q_gpm_data) if q_gpm_data else 0
        
        passes = comp_time_min is not None and comp_time_min <= TIME_LIMIT_MIN
        
        # If didn't complete within sim time
        if comp_time_min is None:
            status = "DID NOT COMPLETE"
        elif passes:
            status = "PASS"
        else:
            status = "FAIL"
        
        results.append({
            'name': name,
            'viscosity': visc,
            'sg': sg,
            'loads': loads,
            'completion_time_min': comp_time_min,
            'avg_gpm': avg_gpm,
            'simple_gpm': simple_gpm,
            'peak_gpm': peak_gpm,
            'passes': passes,
            'status': status,
            'vol_at_90': v90,
            'pct_at_90': pct90,
            'sim_end_time_min': times[-1] / 60 if times else 0,
            'final_transferred_gal': v_transferred[-1] if v_transferred else 0,
        })
    
    # Sort by completion time (None = infinity at bottom)
    results.sort(key=lambda r: r['completion_time_min'] if r['completion_time_min'] else 99999)
    
    # ===== PRINT REPORT =====
    print("=" * 120)
    print("  BULL & BEAR TRUCKING — FLEET COMMODITY UNLOADING SIMULATION REPORT")
    print("  Parameters: 6,500 gal tanker | 19 SCFM air supply | 3\" valve | 3\" × 20ft hose | Gravity + air pressure")
    print("  Time Limit: 1.5 hours (90 minutes)")
    print("=" * 120)
    
    # Summary table
    print(f"\n{'─' * 120}")
    print(f"  {'#':<3} {'Product':<25} {'Visc(cP)':>9} {'SG':>5} {'Loads':>5}  │ {'Time(min)':>10} {'Avg GPM':>8} {'Peak GPM':>9} {'Status':>8}  │ {'@90min':>7} {'%Done':>6}")
    print(f"{'─' * 120}")
    
    pass_count = 0
    fail_count = 0
    
    for i, r in enumerate(results, 1):
        comp = f"{r['completion_time_min']:.1f}" if r['completion_time_min'] else "N/A"
        avg = f"{r['avg_gpm']:.1f}" if r['avg_gpm'] else "0.0"
        peak = f"{r['peak_gpm']:.1f}" if r.get('peak_gpm') else "0.0"
        
        if r['status'] == 'PASS':
            marker = "  ✅"
            pass_count += 1
        elif r['status'] == 'FAIL':
            marker = "  ❌"
            fail_count += 1
        else:
            marker = "  ⛔"
            fail_count += 1
        
        v90_str = f"{r['vol_at_90']:.0f}" if r['vol_at_90'] else "0"
        pct_str = f"{r['pct_at_90']:.1f}%" if r['pct_at_90'] else "0.0%"
        
        print(f"  {i:<3} {r['name']:<25} {r['viscosity']:>9.1f} {r['sg']:>5.3f} {r['loads']:>5}  │ {comp:>10} {avg:>8} {peak:>9} {r['status']:>8}{marker}  │ {v90_str:>7} {pct_str:>6}")
    
    print(f"{'─' * 120}")
    
    # Summary stats
    print(f"\n{'=' * 80}")
    print(f"  SUMMARY")
    print(f"{'=' * 80}")
    print(f"  Total Products Simulated:  {len(results)}")
    print(f"  PASS (≤ 90 min):           {pass_count}  ({pass_count/len(results)*100:.0f}%)")
    print(f"  FAIL (> 90 min):           {fail_count}  ({fail_count/len(results)*100:.0f}%)")
    
    # Separate pass and fail lists
    passers = [r for r in results if r['status'] == 'PASS']
    failers = [r for r in results if r['status'] != 'PASS']
    
    if passers:
        avg_time_pass = sum(r['completion_time_min'] for r in passers) / len(passers)
        print(f"\n  Fastest Product:           {passers[0]['name']} @ {passers[0]['completion_time_min']:.1f} min ({passers[0]['avg_gpm']:.1f} GPM avg)")
        print(f"  Slowest PASS Product:      {passers[-1]['name']} @ {passers[-1]['completion_time_min']:.1f} min ({passers[-1]['avg_gpm']:.1f} GPM avg)")
        print(f"  Average Time (PASS only):  {avg_time_pass:.1f} min")
    
    # Products that FAIL
    if failers:
        print(f"\n{'=' * 80}")
        print(f"  PRODUCTS EXCEEDING 1.5-HOUR LIMIT")
        print(f"{'=' * 80}")
        for r in failers:
            comp = f"{r['completion_time_min']:.1f} min" if r['completion_time_min'] else "Did not complete"
            hrs = r['completion_time_min'] / 60 if r['completion_time_min'] else None
            hrs_str = f" ({hrs:.1f} hrs)" if hrs else ""
            print(f"  ❌ {r['name']:<25} {r['viscosity']:>7.0f} cP  →  {comp}{hrs_str}")
            print(f"     At 90 min: {r['pct_at_90']:.1f}% transferred ({r['vol_at_90']:.0f} gal of 6,500)")
            print(f"     Avg GPM: {r['avg_gpm']:.1f}  |  Peak GPM: {r.get('peak_gpm', 0):.1f}")
            if r['completion_time_min']:
                extra = r['completion_time_min'] - TIME_LIMIT_MIN
                print(f"     Over limit by: {extra:.1f} min ({extra/60:.1f} hrs)")
            print()
    
    # Viscosity vs Time analysis
    print(f"\n{'=' * 80}")
    print(f"  VISCOSITY vs UNLOADING TIME ANALYSIS")
    print(f"{'=' * 80}")
    print(f"  {'Viscosity Range':<25} {'Products':>8} {'Avg Time':>10} {'Avg GPM':>9} {'All Pass?':>10}")
    print(f"  {'─'*25} {'─'*8:>8} {'─'*10:>10} {'─'*9:>9} {'─'*10:>10}")
    
    ranges = [
        ("< 10 cP (water-like)", lambda v: v < 10),
        ("10-50 cP (light oil)", lambda v: 10 <= v < 50),
        ("50-200 cP (med oil)", lambda v: 50 <= v < 200),
        ("200-500 cP (heavy oil)", lambda v: 200 <= v < 500),
        ("500-1000 cP (syrup)", lambda v: 500 <= v < 1000),
        ("1000-5000 cP (honey)", lambda v: 1000 <= v < 5000),
        ("> 5000 cP (nightmare)", lambda v: v >= 5000),
    ]
    
    for label, cond in ranges:
        group = [r for r in results if cond(r['viscosity'])]
        if group:
            times_valid = [r['completion_time_min'] for r in group if r['completion_time_min']]
            avg_t = sum(times_valid) / len(times_valid) if times_valid else 0
            avg_g = sum(r['avg_gpm'] for r in group) / len(group)
            all_pass = all(r['status'] == 'PASS' for r in group)
            print(f"  {label:<25} {len(group):>8} {avg_t:>9.1f}m {avg_g:>8.1f} {'  YES ✅' if all_pass else '  NO  ❌':>10}")
    
    # Fleet impact analysis
    print(f"\n{'=' * 80}")
    print(f"  FLEET OPERATIONS IMPACT")  
    print(f"{'=' * 80}")
    total_loads = sum(r['loads'] for r in results)
    pass_loads = sum(r['loads'] for r in results if r['status'] == 'PASS')
    fail_loads = sum(r['loads'] for r in results if r['status'] != 'PASS')
    print(f"  Total annual loads (top 20):    {total_loads}")
    print(f"  Loads within 90-min limit:      {pass_loads} ({pass_loads/total_loads*100:.1f}%)")
    print(f"  Loads exceeding 90-min limit:   {fail_loads} ({fail_loads/total_loads*100:.1f}%)")
    
    if failers:
        print(f"\n  Problem loads breakdown:")
        for r in failers:
            print(f"    {r['name']:<25} {r['loads']:>4} loads/yr  ({r['loads']/total_loads*100:.1f}% of top-20 volume)")
    
    # GPM Report sorted by GPM
    print(f"\n{'=' * 80}")
    print(f"  GPM RANKINGS (All Products)")
    print(f"{'=' * 80}")
    by_gpm = sorted(results, key=lambda r: r['avg_gpm'], reverse=True)
    print(f"  {'#':<3} {'Product':<25} {'Visc(cP)':>9} {'Avg GPM':>9} {'Peak GPM':>10} {'Time(min)':>10}")
    print(f"  {'─'*3} {'─'*25} {'─'*9} {'─'*9} {'─'*10} {'─'*10}")
    for i, r in enumerate(by_gpm, 1):
        comp = f"{r['completion_time_min']:.1f}" if r['completion_time_min'] else "N/A"
        print(f"  {i:<3} {r['name']:<25} {r['viscosity']:>9.1f} {r['avg_gpm']:>9.1f} {r.get('peak_gpm',0):>10.1f} {comp:>10}")
    
    print(f"\n{'=' * 80}")
    print(f"  KEY FINDINGS")
    print(f"{'=' * 80}")
    
    # Critical viscosity threshold
    # Find the boundary where products start failing
    sorted_by_visc = sorted(results, key=lambda r: r['viscosity'])
    last_pass_visc = 0
    first_fail_visc = 99999
    for r in sorted_by_visc:
        if r['status'] == 'PASS':
            last_pass_visc = max(last_pass_visc, r['viscosity'])
        else:
            first_fail_visc = min(first_fail_visc, r['viscosity'])
    
    print(f"  • Critical viscosity threshold: ~{last_pass_visc:.0f}-{first_fail_visc:.0f} cP")
    print(f"    Products ≤ {last_pass_visc:.0f} cP complete within 90 min")
    print(f"    Products ≥ {first_fail_visc:.0f} cP exceed the time limit")
    
    if passers:
        fastest = passers[0]
        slowest = passers[-1]
        print(f"  • Fastest: {fastest['name']} ({fastest['viscosity']} cP) → {fastest['completion_time_min']:.1f} min at {fastest['avg_gpm']:.1f} GPM")
        print(f"  • Slowest PASS: {slowest['name']} ({slowest['viscosity']} cP) → {slowest['completion_time_min']:.1f} min at {slowest['avg_gpm']:.1f} GPM")
    
    if failers:
        worst = max(failers, key=lambda r: r['viscosity'])
        print(f"  • Worst: {worst['name']} ({worst['viscosity']} cP) → {'%.1f min' % worst['completion_time_min'] if worst['completion_time_min'] else 'N/A'}")
    
    print(f"\n  With 19 SCFM air supply + gravity on a standard 6,500 gal tanker:")
    print(f"  {pass_count} of {len(results)} products ({pass_count/len(results)*100:.0f}%) meet the 1.5-hour target")
    print(f"  {pass_loads} of {total_loads} annual loads ({pass_loads/total_loads*100:.1f}%) can be unloaded within 90 min")
    print()

if __name__ == "__main__":
    main()
