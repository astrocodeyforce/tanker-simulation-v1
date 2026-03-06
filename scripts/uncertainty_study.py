#!/usr/bin/env python3
"""
uncertainty_study.py — RSS Uncertainty Propagation (White's Fluid Mechanics Eq. E.1/E.2)

For each representative product, perturb 7 input parameters one at a time
and measure the effect on completion time. Then combine via RSS:

    δt = √[ Σ (∂t/∂xi · δxi)² ]           ... Eq. E.1

Sensitivities via central finite difference:
    ∂t/∂xi ≈ [t(xi+δ) - t(xi-δ)] / (2δ)

Parameters & assumed measurement uncertainties:
    μ  (viscosity)       ±15%   — lab measurement spread
    D  (pipe diameter)   ±2%    — manufacturing tolerance
    SCFM (air supply)    ±5%    — compressor gauge accuracy
    V  (initial volume)  ±3%    — tank gauge (dipstick) accuracy
    ρ  (liquid density)  ±2%    — hydrometer / SG accuracy
    K  (minor losses)    ±20%   — fitting geometry uncertainty
    Δz (elevation)       ±0.5ft — site survey accuracy (absolute)

Products: OCD (0.6 cP), Resin Solution (500 cP), Tall Oil Rosin (5000 cP)
"""

import os
import sys
import csv
import re
import subprocess
import math
import json
from datetime import datetime

BASE_DIR = "/opt/sim-lab/truck-tanker-sim-env"
CONFIG_DIR = os.path.join(BASE_DIR, "config")
RUNS_DIR = os.path.join(BASE_DIR, "data", "runs")

# ── Representative products (low / medium / high viscosity) ──
PRODUCTS = {
    "ocd":             {"base_yaml": "fleet_ocd.yaml",             "label": "OCD (0.6 cP)"},
    "resin_solution":  {"base_yaml": "fleet_resin_solution.yaml",  "label": "Resin Solution (500 cP)"},
    "tall_oil_rosin":  {"base_yaml": "fleet_tall_oil_rosin.yaml",  "label": "Tall Oil Rosin (5000 cP)"},
}

# ── Parameters to perturb: (yaml_key(s), fractional_uncertainty, is_absolute, label) ──
# For multi-key params (D, K), all matching keys are scaled together.
PARAMS = [
    {
        "name": "mu",
        "label": "Viscosity (μ)",
        "keys": ["liquid_viscosity_cP"],
        "delta_frac": 0.15,
        "absolute": False,
    },
    {
        "name": "D",
        "label": "Pipe diameter (D)",
        "keys": ["pipe1_diameter_in", "pipe2_diameter_in", "pipe3_diameter_in", "valve_diameter_in"],
        "delta_frac": 0.02,
        "absolute": False,
    },
    {
        "name": "SCFM",
        "label": "Air supply (SCFM)",
        "keys": ["air_supply_scfm"],
        "delta_frac": 0.05,
        "absolute": False,
    },
    {
        "name": "V",
        "label": "Initial volume (V)",
        "keys": ["initial_liquid_volume_gal"],
        "delta_frac": 0.03,
        "absolute": False,
    },
    {
        "name": "rho",
        "label": "Density (ρ)",
        "keys": ["liquid_density_kg_m3"],
        "delta_frac": 0.02,
        "absolute": False,
    },
    {
        "name": "K",
        "label": "Minor losses (K)",
        "keys": ["pipe1_K_minor", "pipe2_K_minor", "pipe3_K_minor", "valve_K_open"],
        "delta_frac": 0.20,
        "absolute": False,
    },
    {
        "name": "dz",
        "label": "Elevation (Δz)",
        "keys": ["elevation_change_ft"],
        "delta_frac": None,   # absolute perturbation
        "delta_abs": 0.5,     # ±0.5 ft
        "absolute": True,
    },
]


def parse_yaml(path):
    """Simple YAML parser (no pyyaml dependency)."""
    config = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^(\w+)\s*:\s*(.+)$', line)
            if m:
                key = m.group(1)
                val = m.group(2).strip()
                if not val.startswith('"') and not val.startswith("'"):
                    val = re.split(r'\s+#', val, maxsplit=1)[0].strip()
                val = val.strip('"').strip("'")
                try:
                    if "." in val:
                        config[key] = float(val)
                    else:
                        config[key] = int(val)
                except ValueError:
                    config[key] = val
    return config


def write_yaml(config, path, comment=""):
    """Write config dict as YAML."""
    with open(path, "w") as f:
        if comment:
            f.write(f"# {comment}\n")
        for key, val in config.items():
            if isinstance(val, float):
                f.write(f"{key}: {val}\n")
            else:
                f.write(f"{key}: {val}\n")


def run_simulation(yaml_path):
    """Run simulation and return output CSV path."""
    cmd = [
        "docker", "compose", "run", "--rm", "-T", "--entrypoint", "",
        "openmodelica-runner", "bash",
        "/work/scripts/run_scenario_v2.sh",
        f"/work/config/{os.path.basename(yaml_path)}"
    ]
    result = subprocess.run(
        cmd, cwd=BASE_DIR, capture_output=True, text=True,
        stdin=subprocess.DEVNULL, timeout=600
    )
    # Extract output path from stdout
    for line in result.stdout.split("\n"):
        if "outputs.csv" in line and "Output:" in line:
            csv_path = line.split("Output:")[-1].strip()
            csv_path = csv_path.replace("/work/", BASE_DIR + "/")
            return csv_path
    # Try to find most recent run
    print(f"  WARNING: Could not parse output path. stdout={result.stdout[-200:]}", file=sys.stderr)
    return None


def extract_completion_time(csv_path):
    """Extract completion time in minutes from output CSV."""
    rows = []
    with open(csv_path) as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows.append([float(x) for x in row])
    h = {name: i for i, name in enumerate(header)}
    v0 = rows[0][h["V_liquid_gal"]]
    threshold = v0 * 0.005  # 99.5% transferred
    comp_time = rows[-1][h["time"]]
    for row in rows:
        if row[h["V_liquid_gal"]] <= threshold:
            comp_time = row[h["time"]]
            break
    return comp_time / 60.0  # minutes


def perturb_config(base_config, param, direction):
    """Create perturbed config. direction = +1 or -1."""
    config = dict(base_config)
    for key in param["keys"]:
        if key not in config:
            continue
        base_val = config[key]
        if param["absolute"]:
            delta = param["delta_abs"]
            config[key] = base_val + direction * delta
        else:
            delta = base_val * param["delta_frac"]
            config[key] = base_val + direction * delta
    return config


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {}

    total_sims = len(PRODUCTS) * (1 + 2 * len(PARAMS))  # base + 2 per param
    sim_count = 0

    for prod_key, prod_info in PRODUCTS.items():
        base_yaml_path = os.path.join(CONFIG_DIR, prod_info["base_yaml"])
        base_config = parse_yaml(base_yaml_path)
        prod_results = {"label": prod_info["label"], "params": {}}

        # Run base case
        sim_count += 1
        print(f"\n[{sim_count}/{total_sims}] {prod_info['label']} — BASE")
        base_config["scenario_name"] = f"unc_{prod_key}_base"
        unc_yaml = os.path.join(CONFIG_DIR, f"unc_{prod_key}_base.yaml")
        write_yaml(base_config, unc_yaml, f"Uncertainty study — {prod_info['label']} — BASE")

        csv_path = run_simulation(unc_yaml)
        if csv_path is None:
            print(f"  FAILED — skipping product", file=sys.stderr)
            continue
        t_base = extract_completion_time(csv_path)
        prod_results["t_base_min"] = t_base
        print(f"  t_base = {t_base:.2f} min")

        # Perturb each parameter
        for param in PARAMS:
            sensitivities = {}

            for direction, label in [(+1, "plus"), (-1, "minus")]:
                sim_count += 1
                scenario_name = f"unc_{prod_key}_{param['name']}_{label}"
                print(f"[{sim_count}/{total_sims}] {prod_info['label']} — {param['label']} {label}")

                perturbed = perturb_config(base_config, param, direction)
                perturbed["scenario_name"] = scenario_name
                unc_yaml = os.path.join(CONFIG_DIR, f"{scenario_name}.yaml")
                write_yaml(perturbed, unc_yaml, f"Uncertainty study — {prod_info['label']} — {param['label']} {label}")

                csv_path = run_simulation(unc_yaml)
                if csv_path is None:
                    print(f"  FAILED", file=sys.stderr)
                    sensitivities[label] = None
                    continue
                t_pert = extract_completion_time(csv_path)
                sensitivities[label] = t_pert
                print(f"  t = {t_pert:.2f} min")

            # Central finite-difference sensitivity
            t_plus = sensitivities.get("plus")
            t_minus = sensitivities.get("minus")
            if t_plus is not None and t_minus is not None:
                if param["absolute"]:
                    delta_x = param["delta_abs"]
                    dtdx = (t_plus - t_minus) / (2 * delta_x)
                    contribution = dtdx * delta_x  # δt_i = (∂t/∂x) · δx
                else:
                    # For fractional: perturb is ±frac*x0
                    # sensitivity = dt / (2 * frac * x0)
                    # contribution = sensitivity * frac * x0 = (t+ - t-) / 2
                    contribution = (t_plus - t_minus) / 2.0

                prod_results["params"][param["name"]] = {
                    "label": param["label"],
                    "t_plus": t_plus,
                    "t_minus": t_minus,
                    "contribution_min": contribution,
                    "contribution_sq": contribution ** 2,
                }

        # RSS total
        sum_sq = sum(p["contribution_sq"] for p in prod_results["params"].values())
        rss_total = math.sqrt(sum_sq)
        prod_results["rss_total_min"] = rss_total
        prod_results["rss_pct"] = (rss_total / t_base * 100) if t_base > 0 else 0

        results[prod_key] = prod_results

    # ── Print summary report ──
    print("\n" + "=" * 95)
    print("UNCERTAINTY STUDY — RSS Propagation (White's Eq. E.1)")
    print("=" * 95)

    for prod_key, pr in results.items():
        print(f"\n{'─' * 95}")
        print(f"  {pr['label']}   |   Base completion time: {pr['t_base_min']:.1f} min")
        print(f"{'─' * 95}")
        print(f"  {'Parameter':<22} {'t⁻ (min)':>10} {'t_base':>10} {'t⁺ (min)':>10} {'δt_i (min)':>10} {'(δt_i)²':>10} {'% of Σ':>8}")
        print(f"  {'─'*22} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*8}")

        sum_sq = sum(p["contribution_sq"] for p in pr["params"].values())

        for pname, pdata in sorted(pr["params"].items(), key=lambda x: -abs(x[1]["contribution_sq"])):
            pct = (pdata["contribution_sq"] / sum_sq * 100) if sum_sq > 0 else 0
            print(f"  {pdata['label']:<22} {pdata['t_minus']:>10.2f} {pr['t_base_min']:>10.2f} {pdata['t_plus']:>10.2f} {pdata['contribution_min']:>+10.2f} {pdata['contribution_sq']:>10.3f} {pct:>7.1f}%")

        print(f"  {'─'*22} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*8}")
        print(f"  {'RSS TOTAL':<22} {'':>10} {'':>10} {'':>10} {pr['rss_total_min']:>+10.2f} {sum_sq:>10.3f} {'100.0%':>8}")
        print(f"  RSS uncertainty: ±{pr['rss_total_min']:.2f} min  ({pr['rss_pct']:.1f}% of base time)")

    # ── Save JSON ──
    json_path = os.path.join(BASE_DIR, "data", f"uncertainty_results_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved: {json_path}")

    # ── Eq. E.2 cross-check for Darcy-Weisbach (turbulent power-law) ──
    print("\n" + "=" * 95)
    print("CROSS-CHECK: Eq. E.2 Power-Law Approximation for Completion Time")
    print("  For turbulent flow: t ∝ μ^0 · D^(-5) · V^1 · ρ^(-0.5) · K^0.5 (approximate)")
    print("  δt/t = √[ Σ (n_i · δx_i/x_i)² ]")
    print("=" * 95)


if __name__ == "__main__":
    main()
