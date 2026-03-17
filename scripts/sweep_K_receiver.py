#!/usr/bin/env python3
"""Sweep K_pipe2 (2" receiver valve section) to find what matches driver data."""
import subprocess, yaml, shutil, pandas as pd, os, tempfile, sys

BASE_CONFIG = "/opt/sim-lab/truck-tanker-sim-env/config/app_1700cP_corrected.yaml"
DRIVER = {"time_min": 100, "P_10min": 18, "P_35min": 15}

# K values to sweep on the 2" receiver section
K_VALUES = [1.48, 3.0, 5.0, 8.0, 12.0, 16.0, 20.0]

results = []
for k in K_VALUES:
    # Create temp config
    with open(BASE_CONFIG) as f:
        cfg = yaml.safe_load(f)
    cfg["pipe2_K_minor"] = k
    cfg["scenario_name"] = f"sweep_K_{k:.1f}"

    tmp_cfg = f"/opt/sim-lab/truck-tanker-sim-env/config/_sweep_k_{k:.1f}.yaml"
    with open(tmp_cfg, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)

    # Run sim
    cmd = [
        "docker", "compose", "run", "--rm", "--entrypoint", "",
        "openmodelica-runner", "bash",
        "/work/scripts/run_scenario_v2.sh", f"/work/config/_sweep_k_{k:.1f}.yaml"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          cwd="/opt/sim-lab/truck-tanker-sim-env", timeout=300)

    # Find output dir
    for line in proc.stdout.splitlines():
        if "Output:" in line:
            csv_path = line.split("Output:")[1].strip().replace("/work/", "/opt/sim-lab/truck-tanker-sim-env/")
            break
    else:
        print(f"K={k:.1f}: FAILED")
        continue

    df = pd.read_csv(csv_path)
    df["P_psig"] = df["P_gauge"] / 6894.76

    flow = df["Q_L_gpm"] > 0.1
    if flow.any():
        comp_s = df.loc[flow[::-1].idxmax(), "time"]
    else:
        comp_s = df["time"].iloc[-1]
    comp_min = comp_s / 60.0

    p10 = df.iloc[(df["time"] - 600).abs().idxmin()]["P_psig"]
    p35 = df.iloc[(df["time"] - 2100).abs().idxmin()]["P_psig"]
    peak = df["Q_L_gpm"].max()

    results.append({"K_pipe2": k, "time_min": comp_min, "P_10": p10, "P_35": p35, "peak_GPM": peak})
    print(f"K={k:5.1f} | time={comp_min:5.1f} min | P@10m={p10:5.1f} | P@35m={p35:5.1f} | peak={peak:5.1f} GPM")

    # Cleanup temp config
    os.remove(tmp_cfg)

# Summary
print(f"\n{'K_pipe2':>8} {'Time(min)':>10} {'P@10m':>8} {'P@35m':>8} {'Peak GPM':>10} {'Err(time)':>10}")
print("-" * 60)
for r in results:
    err = (r["time_min"] - 100) / 100 * 100
    print(f"{r['K_pipe2']:>8.1f} {r['time_min']:>10.1f} {r['P_10']:>8.1f} {r['P_35']:>8.1f} {r['peak_GPM']:>10.1f} {err:>9.1f}%")
print(f"{'DRIVER':>8} {'100':>10} {'18.0':>8} {'15.0':>8}")

# Interpolate K for 100 min
if len(results) >= 2:
    import numpy as np
    ks = [r["K_pipe2"] for r in results]
    ts = [r["time_min"] for r in results]
    if min(ts) < 100 < max(ts):
        k_interp = np.interp(100, ts, ks)
        print(f"\n>>> Interpolated K_pipe2 for 100 min: {k_interp:.1f}")
    elif max(ts) < 100:
        print(f"\n>>> Need higher K values — max time was {max(ts):.1f} min at K={ks[ts.index(max(ts))]:.1f}")
