#!/usr/bin/env python3
"""
3D Decision Matrix Sweep: Hose Diameter × Compressor SCFM × Viscosity
----------------------------------------------------------------------
Produces a CSV with discharge time, peak GPM, and avg pressure for every combo.
"""
import subprocess, yaml, pandas as pd, os, sys, time, csv
from itertools import product

# ── Sweep dimensions ──────────────────────────────────────────────
HOSE_DIAMETERS = [2.0, 3.0]                                    # inches
SCFM_VALUES    = [10, 15, 17, 19, 25, 30, 35, 40, 55, 60]      # SCFM
VISCOSITIES    = [1, 50, 100, 500, 1000, 2000, 5000]            # cP

TOTAL = len(HOSE_DIAMETERS) * len(SCFM_VALUES) * len(VISCOSITIES)

# ── Base config (clean single-pipe, no receiver restriction) ──────
BASE = {
    "scenario_name": "sweep",
    "tank_total_volume_gal": 7000,
    "tank_diameter_in": 68.0,
    "tank_length_ft": 35.5,
    "initial_liquid_volume_gal": 5255,
    "initial_tank_pressure_psig": 20.0,
    "gas_temperature_C": 20.0,
    "ambient_pressure_psia": 14.696,
    "max_tank_pressure_psig": 25.0,
    "relief_valve_pressure_psig": 27.5,
    "relief_valve_Cd": 0.62,
    "relief_valve_diameter_in": 1.0,
    "liquid_density_kg_m3": 1000.0,
    "liquid_viscosity_cP": 1.0,
    "valve_diameter_in": 3.0,
    "valve_K_open": 0.2,
    "valve_opening_fraction": 1.0,
    # Single pipe segment = the hose
    "num_pipes": 1,
    "pipe1_diameter_in": 3.0,
    "pipe1_length_ft": 20.0,
    "pipe1_roughness_mm": 0.015,
    # K = entry(0.5) + 2×cam-lock(0.2) + exit(1.0) = 1.7
    "pipe1_K_minor": 1.7,
    "pipe2_diameter_in": 3.0, "pipe2_length_ft": 0.0, "pipe2_roughness_mm": 0.01, "pipe2_K_minor": 0.0,
    "pipe3_diameter_in": 3.0, "pipe3_length_ft": 0.0, "pipe3_roughness_mm": 0.01, "pipe3_K_minor": 0.0,
    "pipe4_diameter_in": 3.0, "pipe4_length_ft": 0.0, "pipe4_roughness_mm": 0.01, "pipe4_K_minor": 0.0,
    "pipe5_diameter_in": 3.0, "pipe5_length_ft": 0.0, "pipe5_roughness_mm": 0.01, "pipe5_K_minor": 0.0,
    "elevation_change_ft": 0.0,
    "receiver_pressure_psig": 0.0,
    "n_power_law": 1.0,
    "outlet_diameter_in": 3.0,
    "stop_time_s": 14400,      # 4 hours max
    "output_interval_s": 2.0,  # 2s intervals to keep CSV smaller
    "min_liquid_volume_gal": 1,
}

WORKSPACE = "/opt/sim-lab/truck-tanker-sim-env"
CONFIG_DIR = os.path.join(WORKSPACE, "config")
RESULTS_CSV = os.path.join(WORKSPACE, "data", "sweep_3d_results.csv")

def run_one(hose_d, scfm, visc, run_num):
    """Run a single simulation and return results dict."""
    cfg = dict(BASE)
    cfg["scenario_name"] = f"sw_{hose_d:.0f}in_{scfm}scfm_{visc}cP"
    cfg["air_supply_scfm"] = float(scfm)
    cfg["liquid_viscosity_cP"] = float(visc)
    cfg["pipe1_diameter_in"] = float(hose_d)
    cfg["outlet_diameter_in"] = float(hose_d)

    # Adjust valve diameter to match hose (realistic: valve = hose size)
    cfg["valve_diameter_in"] = float(hose_d)

    # For high viscosity / low SCFM, allow longer sim time
    if visc >= 2000 and scfm <= 15:
        cfg["stop_time_s"] = 21600   # 6 hours

    tag = f"{hose_d:.0f}in_{scfm}scfm_{visc}cP"
    tmp_cfg = os.path.join(CONFIG_DIR, f"_sweep_{tag}.yaml")

    with open(tmp_cfg, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)

    cmd = [
        "docker", "compose", "run", "--rm", "--entrypoint", "",
        "openmodelica-runner", "bash",
        "/work/scripts/run_scenario_v2.sh", f"/work/config/_sweep_{tag}.yaml"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=WORKSPACE, timeout=600)
    except subprocess.TimeoutExpired:
        os.remove(tmp_cfg)
        return {"hose_in": hose_d, "scfm": scfm, "visc_cP": visc,
                "time_min": None, "peak_gpm": None, "note": "TIMEOUT"}

    # Find output CSV
    csv_path = None
    for line in proc.stdout.splitlines():
        if "Output:" in line:
            csv_path = line.split("Output:")[1].strip().replace(
                "/work/", WORKSPACE + "/")
            break

    if csv_path is None or not os.path.exists(csv_path):
        os.remove(tmp_cfg)
        return {"hose_in": hose_d, "scfm": scfm, "visc_cP": visc,
                "time_min": None, "peak_gpm": None, "note": "FAILED"}

    df = pd.read_csv(csv_path)
    flow_mask = df["Q_L_gpm"] > 0.1
    if flow_mask.any():
        last_idx = flow_mask[::-1].idxmax()
        comp_s = df.loc[last_idx, "time"]
    else:
        comp_s = df["time"].iloc[-1]

    comp_min = comp_s / 60.0
    peak_gpm = df["Q_L_gpm"].max()

    # Check if sim hit the time limit without finishing
    note = ""
    if df["V_liquid_gal"].iloc[-1] > 10:
        note = f"DNF ({df['V_liquid_gal'].iloc[-1]:.0f} gal left)"
        comp_min = None

    os.remove(tmp_cfg)

    return {"hose_in": hose_d, "scfm": scfm, "visc_cP": visc,
            "time_min": comp_min, "peak_gpm": peak_gpm, "note": note}


def main():
    combos = list(product(HOSE_DIAMETERS, SCFM_VALUES, VISCOSITIES))
    print(f"=== 3D Sweep: {len(combos)} simulations ===")
    print(f"Hose: {HOSE_DIAMETERS}")
    print(f"SCFM: {SCFM_VALUES}")
    print(f"Visc: {VISCOSITIES}")
    print()

    results = []
    t0 = time.time()

    for i, (hose, scfm, visc) in enumerate(combos, 1):
        elapsed = time.time() - t0
        rate = elapsed / max(i - 1, 1)
        eta = rate * (len(combos) - i + 1)
        print(f"[{i:3d}/{len(combos)}] {hose:.0f}\" | {scfm:2d} SCFM | {visc:5d} cP "
              f"(ETA: {eta/60:.0f} min) ... ", end="", flush=True)

        r = run_one(hose, scfm, visc, i)
        results.append(r)

        if r["time_min"] is not None:
            print(f"{r['time_min']:6.1f} min | {r['peak_gpm']:5.1f} GPM")
        else:
            print(f"  {r['note']}")

    # Write results CSV
    df_out = pd.DataFrame(results)
    df_out.to_csv(RESULTS_CSV, index=False)
    print(f"\nResults saved: {RESULTS_CSV}")
    print(f"Total time: {(time.time()-t0)/60:.1f} min")

    # Print summary tables
    print("\n" + "=" * 70)
    print("DISCHARGE TIME (minutes) — 2\" hose")
    print("=" * 70)
    print_table(df_out, 2.0)

    print("\n" + "=" * 70)
    print("DISCHARGE TIME (minutes) — 3\" hose")
    print("=" * 70)
    print_table(df_out, 3.0)

    print("\n" + "=" * 70)
    print("TIME SAVED by upgrading 2\" → 3\" hose (minutes)")
    print("=" * 70)
    print_diff_table(df_out)


def print_table(df, hose):
    sub = df[df["hose_in"] == hose]
    pivot = sub.pivot(index="visc_cP", columns="scfm", values="time_min")
    pivot = pivot.reindex(index=VISCOSITIES, columns=SCFM_VALUES)
    header = f"{'Visc(cP)':>10}" + "".join(f"{s:>8}" for s in SCFM_VALUES)
    print(header)
    print("-" * len(header))
    for v in VISCOSITIES:
        row = f"{v:>10}"
        for s in SCFM_VALUES:
            val = pivot.loc[v, s] if v in pivot.index and s in pivot.columns else None
            if val is not None and not pd.isna(val):
                row += f"{val:>8.1f}"
            else:
                row += f"{'DNF':>8}"
        print(row)


def print_diff_table(df):
    header = f"{'Visc(cP)':>10}" + "".join(f"{s:>8}" for s in SCFM_VALUES)
    print(header)
    print("-" * len(header))
    for v in VISCOSITIES:
        row = f"{v:>10}"
        for s in SCFM_VALUES:
            t2 = df[(df["hose_in"] == 2.0) & (df["scfm"] == s) & (df["visc_cP"] == v)]["time_min"]
            t3 = df[(df["hose_in"] == 3.0) & (df["scfm"] == s) & (df["visc_cP"] == v)]["time_min"]
            if len(t2) and len(t3) and not pd.isna(t2.iloc[0]) and not pd.isna(t3.iloc[0]):
                diff = t2.iloc[0] - t3.iloc[0]
                row += f"{diff:>+8.1f}"
            else:
                row += f"{'N/A':>8}"
        print(row)


if __name__ == "__main__":
    main()
