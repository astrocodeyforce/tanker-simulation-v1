#!/usr/bin/env python3
"""
5D Decision Matrix Sweep
========================
Hose Diameter × SCFM × Viscosity × Initial Volume × Pre-Pressure

Features:
  - Checkpoint/resume: saves after every run, resumes from last completed
  - Rich outputs: discharge time, peak GPM, avg GPM, avg pressure,
    time-to-50%, time-to-90%, energy efficiency
  - Summary tables at the end
"""
import subprocess, yaml, pandas as pd, numpy as np, os, sys, time, json
from itertools import product

# ═══════════════════════════════════════════════════════════════════
#  SWEEP DIMENSIONS
# ═══════════════════════════════════════════════════════════════════
HOSE_DIAMETERS   = [2.0, 3.0]                                   # inches
SCFM_VALUES      = [10, 15, 17, 19, 25, 30, 35, 40, 55, 60]    # SCFM
VISCOSITIES      = [1, 50, 100, 500, 1000, 2000, 5000]          # cP
INIT_VOLUMES     = [5000, 6500]                                  # gallons
PRE_PRESSURES    = [10, 15, 20]                                  # psig

# ═══════════════════════════════════════════════════════════════════
#  BASE CONFIG (overridden per run)
# ═══════════════════════════════════════════════════════════════════
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
    "num_pipes": 1,
    "pipe1_diameter_in": 3.0,
    "pipe1_length_ft": 20.0,
    "pipe1_roughness_mm": 0.015,
    "pipe1_K_minor": 1.7,   # entry(0.5) + 2×cam-lock(0.2) + exit(1.0)
    "pipe2_diameter_in": 3.0, "pipe2_length_ft": 0.0, "pipe2_roughness_mm": 0.01, "pipe2_K_minor": 0.0,
    "pipe3_diameter_in": 3.0, "pipe3_length_ft": 0.0, "pipe3_roughness_mm": 0.01, "pipe3_K_minor": 0.0,
    "pipe4_diameter_in": 3.0, "pipe4_length_ft": 0.0, "pipe4_roughness_mm": 0.01, "pipe4_K_minor": 0.0,
    "pipe5_diameter_in": 3.0, "pipe5_length_ft": 0.0, "pipe5_roughness_mm": 0.01, "pipe5_K_minor": 0.0,
    "elevation_change_ft": 0.0,
    "receiver_pressure_psig": 0.0,
    "n_power_law": 1.0,
    "outlet_diameter_in": 3.0,
    "stop_time_s": 14400,
    "output_interval_s": 2.0,
    "min_liquid_volume_gal": 1,
}

# ═══════════════════════════════════════════════════════════════════
#  PATHS
# ═══════════════════════════════════════════════════════════════════
WORKSPACE    = "/opt/sim-lab/truck-tanker-sim-env"
CONFIG_DIR   = os.path.join(WORKSPACE, "config")
DATA_DIR     = os.path.join(WORKSPACE, "data")
RESULTS_CSV  = os.path.join(DATA_DIR, "sweep_5d_results.csv")
CHECKPOINT   = os.path.join(DATA_DIR, "sweep_5d_checkpoint.json")


def make_run_key(hose_d, scfm, visc, vol, psi):
    """Unique string key for a parameter combo."""
    return f"{hose_d:.0f}in_{scfm}scfm_{visc}cP_{vol}gal_{psi}psi"


def load_checkpoint():
    """Load set of completed run keys."""
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            data = json.load(f)
        return set(data.get("completed", [])), data.get("results", [])
    return set(), []


def save_checkpoint(completed_keys, results):
    """Save checkpoint atomically."""
    tmp = CHECKPOINT + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"completed": list(completed_keys), "results": results}, f)
    os.replace(tmp, CHECKPOINT)


def extract_metrics(csv_path, init_vol_gal):
    """Extract rich metrics from simulation CSV."""
    df = pd.read_csv(csv_path)

    # Pressure in psig
    df["P_psig"] = df["P_gauge"] / 6894.76

    # Flow mask (flowing period)
    flow_mask = df["Q_L_gpm"] > 0.1
    if not flow_mask.any():
        return {"time_min": None, "peak_gpm": 0, "avg_gpm": 0,
                "avg_pressure_psig": 0, "time_50pct_min": None,
                "time_90pct_min": None, "note": "NO_FLOW"}

    # Completion time
    last_flow_idx = flow_mask[::-1].idxmax()
    comp_s = df.loc[last_flow_idx, "time"]
    comp_min = comp_s / 60.0

    # Did it finish?
    remaining = df["V_liquid_gal"].iloc[-1]
    if remaining > 10:
        return {"time_min": None, "peak_gpm": df["Q_L_gpm"].max(),
                "avg_gpm": None, "avg_pressure_psig": None,
                "time_50pct_min": None, "time_90pct_min": None,
                "note": f"DNF ({remaining:.0f} gal left)"}

    # Flowing subset
    df_flow = df[flow_mask]

    # Peak & average GPM
    peak_gpm = df_flow["Q_L_gpm"].max()
    avg_gpm = df_flow["Q_L_gpm"].mean()

    # Average pressure during discharge
    avg_psi = df_flow["P_psig"].mean()

    # Time to 50% unloaded
    target_50 = init_vol_gal * 0.50
    transferred_50 = df[df["V_transferred_gal"] >= target_50]
    time_50 = transferred_50["time"].iloc[0] / 60.0 if len(transferred_50) else None

    # Time to 90% unloaded
    target_90 = init_vol_gal * 0.90
    transferred_90 = df[df["V_transferred_gal"] >= target_90]
    time_90 = transferred_90["time"].iloc[0] / 60.0 if len(transferred_90) else None

    return {
        "time_min": comp_min,
        "peak_gpm": peak_gpm,
        "avg_gpm": avg_gpm,
        "avg_pressure_psig": avg_psi,
        "time_50pct_min": time_50,
        "time_90pct_min": time_90,
        "note": "",
    }


def run_one(hose_d, scfm, visc, vol, psi):
    """Run a single simulation; return results dict."""
    cfg = dict(BASE)
    cfg["scenario_name"] = make_run_key(hose_d, scfm, visc, vol, psi)
    cfg["air_supply_scfm"] = float(scfm)
    cfg["liquid_viscosity_cP"] = float(visc)
    cfg["initial_liquid_volume_gal"] = float(vol)
    cfg["initial_tank_pressure_psig"] = float(psi)
    cfg["pipe1_diameter_in"] = float(hose_d)
    cfg["outlet_diameter_in"] = float(hose_d)
    cfg["valve_diameter_in"] = float(hose_d)

    # Adjust max pressure to be 5 above start (keep relief 2.5 above max)
    cfg["max_tank_pressure_psig"] = float(psi) + 5.0
    cfg["relief_valve_pressure_psig"] = float(psi) + 7.5

    # For high viscosity / low SCFM, allow longer sim time
    if visc >= 2000 and scfm <= 15:
        cfg["stop_time_s"] = 21600  # 6 hours
    if visc >= 5000:
        cfg["stop_time_s"] = 28800  # 8 hours

    tag = make_run_key(hose_d, scfm, visc, vol, psi)
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
                              cwd=WORKSPACE, timeout=900)
    except subprocess.TimeoutExpired:
        if os.path.exists(tmp_cfg):
            os.remove(tmp_cfg)
        return {"hose_in": hose_d, "scfm": scfm, "visc_cP": visc,
                "vol_gal": vol, "pre_psi": psi,
                "time_min": None, "peak_gpm": None, "avg_gpm": None,
                "avg_pressure_psig": None, "time_50pct_min": None,
                "time_90pct_min": None, "note": "TIMEOUT"}

    # Find output CSV
    csv_path = None
    for line in proc.stdout.splitlines():
        if "Output:" in line:
            csv_path = line.split("Output:")[1].strip().replace(
                "/work/", WORKSPACE + "/")
            break

    if os.path.exists(tmp_cfg):
        os.remove(tmp_cfg)

    if csv_path is None or not os.path.exists(csv_path):
        return {"hose_in": hose_d, "scfm": scfm, "visc_cP": visc,
                "vol_gal": vol, "pre_psi": psi,
                "time_min": None, "peak_gpm": None, "avg_gpm": None,
                "avg_pressure_psig": None, "time_50pct_min": None,
                "time_90pct_min": None, "note": "FAILED"}

    metrics = extract_metrics(csv_path, vol)

    return {
        "hose_in": hose_d,
        "scfm": scfm,
        "visc_cP": visc,
        "vol_gal": vol,
        "pre_psi": psi,
        **metrics,
    }


# ═══════════════════════════════════════════════════════════════════
#  DISPLAY HELPERS
# ═══════════════════════════════════════════════════════════════════
def print_table(df, hose, vol, psi, metric="time_min", label="Discharge Time (min)"):
    """Print a SCFM × Viscosity table for one hose/vol/psi slice."""
    sub = df[(df["hose_in"] == hose) & (df["vol_gal"] == vol) & (df["pre_psi"] == psi)]
    if sub.empty:
        return
    pivot = sub.pivot(index="visc_cP", columns="scfm", values=metric)
    pivot = pivot.reindex(index=VISCOSITIES, columns=SCFM_VALUES)

    print(f"\n  {label}  |  {hose:.0f}\" hose  |  {vol} gal  |  {psi} psig")
    header = f"{'Visc(cP)':>10}" + "".join(f"{s:>8}" for s in SCFM_VALUES)
    print(header)
    print("-" * len(header))
    for v in VISCOSITIES:
        row = f"{v:>10}"
        for s in SCFM_VALUES:
            try:
                val = pivot.loc[v, s]
                if val is not None and not pd.isna(val):
                    row += f"{val:>8.1f}"
                else:
                    row += f"{'DNF':>8}"
            except (KeyError, TypeError):
                row += f"{'---':>8}"
        print(row)


def print_summary(df):
    """Print key summary tables."""
    for vol in INIT_VOLUMES:
        for psi in PRE_PRESSURES:
            for hose in HOSE_DIAMETERS:
                print_table(df, hose, vol, psi, "time_min", "Discharge Time (min)")
            # Diff table
            print(f"\n  TIME SAVED 2\"→3\"  |  {vol} gal  |  {psi} psig")
            header = f"{'Visc(cP)':>10}" + "".join(f"{s:>8}" for s in SCFM_VALUES)
            print(header)
            print("-" * len(header))
            for v in VISCOSITIES:
                row = f"{v:>10}"
                for s in SCFM_VALUES:
                    t2 = df[(df["hose_in"] == 2) & (df["scfm"] == s)
                            & (df["visc_cP"] == v) & (df["vol_gal"] == vol)
                            & (df["pre_psi"] == psi)]["time_min"]
                    t3 = df[(df["hose_in"] == 3) & (df["scfm"] == s)
                            & (df["visc_cP"] == v) & (df["vol_gal"] == vol)
                            & (df["pre_psi"] == psi)]["time_min"]
                    if (len(t2) and len(t3) and
                            not pd.isna(t2.iloc[0]) and not pd.isna(t3.iloc[0])):
                        diff = t2.iloc[0] - t3.iloc[0]
                        row += f"{diff:>+8.1f}"
                    else:
                        row += f"{'N/A':>8}"
                print(row)
            print()


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    combos = list(product(HOSE_DIAMETERS, SCFM_VALUES, VISCOSITIES,
                          INIT_VOLUMES, PRE_PRESSURES))
    total = len(combos)

    # Load checkpoint
    completed_keys, results = load_checkpoint()
    already = len(completed_keys)

    print(f"{'=' * 60}")
    print(f" 5D Decision Matrix Sweep")
    print(f" Hose:     {HOSE_DIAMETERS}")
    print(f" SCFM:     {SCFM_VALUES}")
    print(f" Visc:     {VISCOSITIES}")
    print(f" Volume:   {INIT_VOLUMES}")
    print(f" Pressure: {PRE_PRESSURES}")
    print(f" Total:    {total} runs")
    if already:
        print(f" Resuming: {already} already done, {total - already} remaining")
    print(f"{'=' * 60}\n")

    t0 = time.time()
    done_this_session = 0

    for i, (hose, scfm, visc, vol, psi) in enumerate(combos, 1):
        key = make_run_key(hose, scfm, visc, vol, psi)

        # Skip if already completed
        if key in completed_keys:
            continue

        done_this_session += 1
        remaining = total - already - done_this_session + 1
        if done_this_session > 1:
            elapsed = time.time() - t0
            rate = elapsed / (done_this_session - 1)
            eta_min = rate * remaining / 60
        else:
            eta_min = 0

        print(f"[{already + done_this_session:3d}/{total}] "
              f"{hose:.0f}\" | {scfm:2d} SCFM | {visc:5d} cP | "
              f"{vol} gal | {psi} psig  "
              f"(ETA: {eta_min:.0f} min) ... ", end="", flush=True)

        r = run_one(hose, scfm, visc, vol, psi)
        results.append(r)
        completed_keys.add(key)

        # Checkpoint after every run
        save_checkpoint(completed_keys, results)

        if r["time_min"] is not None:
            extra = ""
            if r.get("time_50pct_min") is not None:
                extra = f" | 50%={r['time_50pct_min']:.0f}m 90%={r['time_90pct_min']:.0f}m"
            print(f"{r['time_min']:6.1f} min | peak {r['peak_gpm']:5.1f} "
                  f"avg {r['avg_gpm']:5.1f} GPM{extra}")
        else:
            print(f"  {r['note']}")

    # Final save
    df_out = pd.DataFrame(results)
    df_out.to_csv(RESULTS_CSV, index=False)

    elapsed_total = (time.time() - t0) / 60
    print(f"\n{'=' * 60}")
    print(f" COMPLETE: {total} runs")
    print(f" This session: {done_this_session} runs in {elapsed_total:.1f} min")
    print(f" Results:  {RESULTS_CSV}")
    print(f"{'=' * 60}")

    # Summary tables
    print_summary(df_out)


if __name__ == "__main__":
    main()
