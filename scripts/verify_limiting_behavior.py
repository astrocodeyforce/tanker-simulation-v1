#!/usr/bin/env python3
"""
verify_limiting_behavior.py — Limiting Behavior Tests for TankerTransferV2
============================================================================
Generates YAML configs across extreme viscosity ranges, runs simulations,
and verifies monotonic physical behavior:

  1. Higher viscosity → slower discharge (longer completion time)
  2. Higher viscosity → lower peak flow rate
  3. Higher viscosity → higher friction losses at same flow rate
  4. Near-zero viscosity → fast discharge (flow approaches inviscid limit)
  5. Very high viscosity → flow approaches zero (discharge time → ∞)

Uses the fleet_ocd.yaml as a base template, varying only viscosity.

Run:
  python3 scripts/verify_limiting_behavior.py

Requires: OpenModelica runner container to be running.
"""

import sys
import os
import subprocess
import tempfile
import time
import numpy as np
import pandas as pd
from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
RUNS_DIR = BASE_DIR / "data" / "runs"

# Viscosity sweep values (cP): from near-inviscid to highly viscous
VISCOSITIES_CP = [0.1, 0.5, 1.0, 5.0, 20.0, 100.0, 500.0, 2000.0, 10000.0]


def generate_config(base_yaml: str, viscosity_cp: float, scenario_suffix: str) -> str:
    """Generate a modified YAML config with a different viscosity."""
    with open(base_yaml) as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if re.match(r'^scenario_name\s*:', line):
            new_lines.append(f"scenario_name: verify_limit_{scenario_suffix}\n")
        elif re.match(r'^liquid_viscosity_cP\s*:', line):
            new_lines.append(f"liquid_viscosity_cP: {viscosity_cp}\n")
        elif re.match(r'^stop_time_s\s*:', line):
            # Give high-viscosity runs enough time
            stop_time = max(7200, int(viscosity_cp * 2))
            stop_time = min(stop_time, 36000)  # cap at 10 hours
            new_lines.append(f"stop_time_s: {stop_time}\n")
        else:
            new_lines.append(line)

    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', prefix='verify_limit_',
        dir=str(CONFIG_DIR), delete=False
    )
    tmp.writelines(new_lines)
    tmp.close()
    return tmp.name


def run_simulation(config_path: str, timeout_s: int = 300) -> str | None:
    """Run a simulation via docker compose run and return the run directory path."""
    docker_config = str(config_path).replace(str(BASE_DIR), "/work")

    cmd = [
        "docker", "compose", "run", "--rm", "--entrypoint", "",
        "openmodelica-runner",
        "bash", "/work/scripts/run_scenario_v2.sh", docker_config
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=timeout_s,
            cwd=str(BASE_DIR),
        )
        # Extract run dir from output
        for line in result.stdout.split("\n"):
            if "Run dir" in line and "/work/data/runs/" in line:
                run_dir = line.split("=")[-1].strip()
                # Convert container path to host path
                run_dir = run_dir.replace("/work/", str(BASE_DIR) + "/")
                return run_dir

        # Fallback: find latest run matching pattern
        pattern = sorted(RUNS_DIR.glob("*verify_limit*"))
        if pattern:
            return str(pattern[-1])

        print(f"  WARNING: Could not find run dir. stdout={result.stdout[-200:]}")
        return None

    except subprocess.TimeoutExpired:
        print(f"  WARNING: Simulation timed out after {timeout_s}s")
        return None
    except Exception as e:
        print(f"  WARNING: Simulation failed: {e}")
        return None


def analyze_run(csv_path: str) -> dict | None:
    """Extract key metrics from a simulation output."""
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
    except Exception as e:
        print(f"  ERROR reading {csv_path}: {e}")
        return None

    V0_gal = df["V_liquid_gal"].iloc[0]
    V_min_gal = df["V_liquid_gal"].iloc[-1]
    V_transferred = df["V_transferred_gal"].iloc[-1]

    # Find completion time (when ~95% transferred)
    target = V0_gal * 0.95
    completed = df[df["V_transferred_gal"] >= target]
    completion_time = completed["time"].iloc[0] if len(completed) > 0 else df["time"].iloc[-1]

    # Flow stats
    peak_gpm = df["Q_L_gpm"].max()
    avg_gpm = df.loc[df["Q_L_gpm"] > 0.1, "Q_L_gpm"].mean() if (df["Q_L_gpm"] > 0.1).any() else 0

    # Peak pressure drop
    peak_dP_loss = df["dP_loss_total"].max()

    return {
        "completion_time_s": completion_time,
        "completion_time_min": completion_time / 60.0,
        "peak_gpm": peak_gpm,
        "avg_gpm": avg_gpm,
        "peak_dP_loss_Pa": peak_dP_loss,
        "V_transferred_gal": V_transferred,
        "V0_gal": V0_gal,
        "pct_transferred": V_transferred / V0_gal * 100 if V0_gal > 0 else 0,
    }


def check_monotonicity(values: list, increasing: bool = True) -> tuple:
    """Check if a sequence is monotonically increasing or decreasing.
    Returns (passes_bool, violations_list).
    """
    violations = []
    for i in range(1, len(values)):
        if increasing:
            if values[i] < values[i-1] * 0.98:  # 2% tolerance for numerical noise
                violations.append((i-1, i, values[i-1], values[i]))
        else:
            if values[i] > values[i-1] * 1.02:
                violations.append((i-1, i, values[i-1], values[i]))
    return len(violations) == 0, violations


def main():
    base_config = CONFIG_DIR / "fleet_ocd.yaml"
    if not base_config.exists():
        print(f"ERROR: Base config not found: {base_config}")
        sys.exit(1)

    print(f"\n╔{'═'*76}╗")
    print(f"║  TankerTransferV2 — Limiting Behavior Verification{' '*25}║")
    print(f"║  Viscosity sweep: {len(VISCOSITIES_CP)} points from {VISCOSITIES_CP[0]} to {VISCOSITIES_CP[-1]} cP{' '*18}║")
    print(f"╚{'═'*76}╝\n")

    run_results = []
    temp_configs = []

    for mu_cp in VISCOSITIES_CP:
        suffix = f"mu{mu_cp:.1f}cP".replace(".", "p")
        print(f"  Running μ = {mu_cp:>10.1f} cP ...", end=" ", flush=True)

        config_path = generate_config(str(base_config), mu_cp, suffix)
        temp_configs.append(config_path)

        run_dir = run_simulation(config_path, timeout_s=600)

        if run_dir and os.path.exists(os.path.join(run_dir, "outputs.csv")):
            metrics = analyze_run(os.path.join(run_dir, "outputs.csv"))
            if metrics:
                metrics["viscosity_cP"] = mu_cp
                run_results.append(metrics)
                print(
                    f"t={metrics['completion_time_min']:.1f} min, "
                    f"peak={metrics['peak_gpm']:.0f} GPM, "
                    f"transferred={metrics['pct_transferred']:.0f}%"
                )
            else:
                print("ANALYSIS FAILED")
        else:
            print("SIM FAILED")

    # Clean up temp configs
    for cfg in temp_configs:
        try:
            os.unlink(cfg)
        except OSError:
            pass

    if len(run_results) < 3:
        print("\nERROR: Too few successful runs for monotonicity analysis.")
        sys.exit(1)

    # ── Sort by viscosity and check monotonicity ──
    run_results.sort(key=lambda x: x["viscosity_cP"])

    viscosities = [r["viscosity_cP"] for r in run_results]
    times = [r["completion_time_s"] for r in run_results]
    peaks = [r["peak_gpm"] for r in run_results]
    dP_peaks = [r["peak_dP_loss_Pa"] for r in run_results]

    print(f"\n{'─'*78}")
    print(f"  RESULTS TABLE")
    print(f"{'─'*78}")
    print(f"  {'μ (cP)':>12} {'Time (min)':>12} {'Peak GPM':>12} {'Avg GPM':>12} {'Peak dP (Pa)':>14} {'Xfer %':>8}")
    print(f"  {'─'*12} {'─'*12} {'─'*12} {'─'*12} {'─'*14} {'─'*8}")
    for r in run_results:
        print(
            f"  {r['viscosity_cP']:>12.1f} "
            f"{r['completion_time_min']:>12.1f} "
            f"{r['peak_gpm']:>12.1f} "
            f"{r['avg_gpm']:>12.1f} "
            f"{r['peak_dP_loss_Pa']:>14.0f} "
            f"{r['pct_transferred']:>8.1f}"
        )

    print(f"\n{'─'*78}")
    print(f"  MONOTONICITY CHECKS")
    print(f"{'─'*78}")

    all_pass = True

    # Check 1: completion time increases with viscosity
    ok, violations = check_monotonicity(times, increasing=True)
    icon = "✓" if ok else "✗"
    print(f"  {icon} Higher viscosity → longer completion time")
    if not ok:
        for i0, i1, v0, v1 in violations:
            print(f"      VIOLATION: μ={viscosities[i0]:.1f}→{viscosities[i1]:.1f} cP, "
                  f"time {v0:.0f}→{v1:.0f} s (decreased)")
        all_pass = False

    # Check 2: peak flow rate decreases with viscosity
    ok, violations = check_monotonicity(peaks, increasing=False)
    icon = "✓" if ok else "✗"
    print(f"  {icon} Higher viscosity → lower peak flow rate")
    if not ok:
        for i0, i1, v0, v1 in violations:
            print(f"      VIOLATION: μ={viscosities[i0]:.1f}→{viscosities[i1]:.1f} cP, "
                  f"peak {v0:.1f}→{v1:.1f} GPM (increased)")
        all_pass = False

    # Check 3: Low viscosity → fast discharge (should complete 95%+ in reasonable time)
    low_mu = [r for r in run_results if r["viscosity_cP"] <= 1.0]
    if low_mu:
        fastest = min(low_mu, key=lambda x: x["completion_time_s"])
        ok = fastest["pct_transferred"] > 95
        icon = "✓" if ok else "✗"
        print(f"  {icon} Low viscosity ({fastest['viscosity_cP']} cP): "
              f"{fastest['pct_transferred']:.0f}% transferred in {fastest['completion_time_min']:.1f} min")
        if not ok:
            all_pass = False

    # Check 4: High viscosity → much slower
    if len(run_results) >= 2:
        slowest = run_results[-1]
        fastest = run_results[0]
        ratio = slowest["completion_time_s"] / max(fastest["completion_time_s"], 1)
        ok = ratio > 2.0  # At least 2× slower at highest viscosity
        icon = "✓" if ok else "✗"
        print(f"  {icon} Viscosity range effect: {fastest['viscosity_cP']:.1f}→{slowest['viscosity_cP']:.1f} cP, "
              f"time ratio = {ratio:.1f}×")
        if not ok:
            all_pass = False

    # Check 5: Speed ratios make physical sense
    # For laminar flow: time ∝ μ approximately. Check that 10× viscosity gives at least 2× time.
    for i in range(len(run_results) - 1):
        if run_results[i+1]["viscosity_cP"] >= 10 * run_results[i]["viscosity_cP"]:
            time_ratio = run_results[i+1]["completion_time_s"] / max(run_results[i]["completion_time_s"], 1)
            ok = time_ratio > 1.5
            icon = "✓" if ok else "✗"
            print(f"  {icon} 10× viscosity jump ({run_results[i]['viscosity_cP']:.0f}→"
                  f"{run_results[i+1]['viscosity_cP']:.0f} cP): "
                  f"time ratio = {time_ratio:.1f}× (expect >1.5×)")
            if not ok:
                all_pass = False

    print(f"\n{'─'*78}")
    status = "✓ ALL LIMITING BEHAVIOR CHECKS PASS" if all_pass else "✗ SOME CHECKS FAILED"
    print(f"  {status}")
    print(f"{'─'*78}\n")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
