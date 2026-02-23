#!/usr/bin/env python3
"""
Parametric Sweep: 3 variables × 50 simulations each = 150 total
Sweep A: Liquid Volume   — 2500 gal × 1.01^n  (n=0..49)
Sweep B: Tank Pressure   — 0.0, 0.5, 1.0, ..., 24.5 psig
Sweep C: Gas Temperature — 15.0 → 40.0 °C  (50 evenly spaced)
Base config: Latex, 1050 kg/m³, 100 cP, 19 SCFM, 3" pipe
"""

import yaml, subprocess, pandas as pd, os, sys, time, shutil, json
import numpy as np

# ── base configuration (latex preset) ──────────────────────────
BASE = {
    'scenario_name': 'sweep',
    'tank_total_volume_gal': 7000,
    'tank_diameter_in': 75.0,
    'tank_length_ft': 30.5,
    'initial_liquid_volume_gal': 6500,
    'initial_tank_pressure_psig': 0.0,
    'gas_temperature_C': 20.0,
    'ambient_pressure_psia': 14.696,
    'max_tank_pressure_psig': 25.0,
    'relief_valve_pressure_psig': 27.5,
    'relief_valve_Cd': 0.62,
    'relief_valve_diameter_in': 1.0,
    'air_supply_scfm': 19.0,
    'liquid_density_kg_m3': 1050.0,
    'liquid_viscosity_cP': 100.0,
    'valve_diameter_in': 3.0,
    'valve_K_open': 0.2,
    'valve_opening_fraction': 1.0,
    'pipe1_diameter_in': 3.0,
    'pipe1_length_ft': 25.0,
    'pipe1_roughness_mm': 0.01,
    'pipe1_K_minor': 1.5,
    'pipe2_diameter_in': 3.0,
    'pipe2_length_ft': 25.0,
    'pipe2_roughness_mm': 0.01,
    'pipe2_K_minor': 1.0,
    'elevation_change_ft': 0.0,
    'receiver_pressure_psig': 0.0,
    'stop_time_s': 5400,
    'output_interval_s': 1.0,
    'min_liquid_volume_gal': 10.0,
}

# ── sweep definitions ─────────────────────────────────────────
# Sweep A: Liquid Volume — 4000 to 6500 gal (typical loading range), 50 steps
liquid_values = list(np.linspace(4000.0, 6500.0, 50))

# Sweep B: Tank Pressure — arithmetic 0, 0.5, 1.0, ..., 24.5
pressure_values = [0.5 * n for n in range(50)]

# Sweep C: Gas Temperature — linspace 15 to 40, 50 points
temp_values = list(np.linspace(15.0, 40.0, 50))

SWEEPS = [
    ('A_liquid_volume', 'initial_liquid_volume_gal', liquid_values, 'gal'),
    ('B_tank_pressure', 'initial_tank_pressure_psig', pressure_values, 'psig'),
    ('C_gas_temperature', 'gas_temperature_C', temp_values, '°C'),
]

# ── paths ──────────────────────────────────────────────────────
WORK = '/work'
CONFIG_PATH = os.path.join(WORK, 'config', 'sweep_tmp.yaml')
RESULTS_DIR = os.path.join(WORK, 'data', 'parametric_sweeps')
os.makedirs(RESULTS_DIR, exist_ok=True)

def run_simulation(cfg: dict, run_id: int = 0) -> dict | None:
    """Write config, run simulation, extract key metrics, clean up.
    Uses unique scenario names + retries to avoid Docker race conditions."""
    import glob as _glob

    tag = f'swp_{run_id:03d}'
    cfg['scenario_name'] = tag
    cfg_path = os.path.join(WORK, 'config', f'{tag}.yaml')
    with open(cfg_path, 'w') as f:
        yaml.dump(cfg, f)

    cmd = [
        'docker', 'compose',
        '--project-directory', '/opt/sim-lab/truck-tanker-sim-env',
        '-f', os.path.join(WORK, 'docker-compose.yml'),
        '--project-name', 'simlab',
        'run', '--rm', '--entrypoint', '',
        'openmodelica-runner',
        'bash', os.path.join(WORK, 'scripts', 'run_scenario_v2.sh'),
        cfg_path,
    ]

    # Retry up to 3 times with delay
    for attempt in range(3):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            time.sleep(2)
            continue

        csvs = sorted(_glob.glob(os.path.join(WORK, 'data', 'runs', f'*{tag}*', 'outputs.csv')))
        if csvs:
            break
        # Wait before retry
        time.sleep(3)
    else:
        # All retries failed — clean up config
        if os.path.exists(cfg_path):
            os.remove(cfg_path)
        return None

    # Clean up config file
    if os.path.exists(cfg_path):
        os.remove(cfg_path)

    df = pd.read_csv(csvs[-1])

    # Extract key metrics
    peak_flow = df['Q_L_gpm'].max()
    peak_pressure = df['P_tank_psig'].max()
    total_transferred = df['V_transferred_gal'].iloc[-1]

    # Find when flow drops below 1 GPM (transfer complete)
    low = df[df['Q_L_gpm'] < 1.0]
    if len(low) > 0 and low.index[0] > 10:
        t_done_s = df.loc[low.index[0], 'time']
    else:
        t_done_s = df['time'].iloc[-1]
    t_done_min = t_done_s / 60.0

    avg_flow = total_transferred / t_done_min if t_done_min > 0 else 0

    # Time to reach peak flow
    peak_idx = df['Q_L_gpm'].idxmax()
    t_peak_min = df.loc[peak_idx, 'time'] / 60.0

    # Flow at t=60s (early-stage indicator)
    row_60 = df[df['time'] >= 60].iloc[0] if len(df[df['time'] >= 60]) > 0 else df.iloc[-1]
    flow_at_1min = row_60['Q_L_gpm']
    pressure_at_1min = row_60['P_tank_psig']

    # Efficiency: gal transferred per minute
    efficiency = total_transferred / t_done_min if t_done_min > 0 else 0

    # Clean up run directory
    run_dir = os.path.dirname(csvs[-1])
    shutil.rmtree(run_dir, ignore_errors=True)

    return {
        'peak_flow_gpm': round(peak_flow, 2),
        'peak_pressure_psig': round(peak_pressure, 2),
        'total_transferred_gal': round(total_transferred, 1),
        'transfer_time_min': round(t_done_min, 2),
        'avg_flow_gpm': round(avg_flow, 2),
        't_peak_flow_min': round(t_peak_min, 2),
        'flow_at_1min_gpm': round(flow_at_1min, 2),
        'pressure_at_1min_psig': round(pressure_at_1min, 2),
        'efficiency_gal_per_min': round(efficiency, 2),
    }


def main():
    # Allow running a single sweep: python parametric_sweep.py A or B or C
    which = sys.argv[1] if len(sys.argv) > 1 else 'ALL'

    for sweep_name, param_key, values, unit in SWEEPS:
        tag = sweep_name[0]  # 'A', 'B', 'C'
        if which != 'ALL' and which != tag:
            continue

        print(f"\n{'='*70}")
        print(f"  SWEEP {sweep_name}: varying {param_key}")
        print(f"  {len(values)} simulations | range: {values[0]:.2f} → {values[-1]:.2f} {unit}")
        print(f"{'='*70}\n")

        rows = []
        for i, val in enumerate(values):
            cfg = BASE.copy()
            cfg[param_key] = round(val, 4)

            run_id = ord(tag) * 100 + i  # unique ID per sweep+iteration
            print(f"  [{i+1:2d}/50] {param_key} = {val:.2f} {unit} ... ", end='', flush=True)
            t0 = time.time()
            result = run_simulation(cfg, run_id=run_id)
            elapsed = time.time() - t0

            if result:
                row = {'run': i+1, param_key: round(val, 4)}
                row.update(result)
                rows.append(row)
                print(f"OK  {elapsed:.0f}s | Flow: {result['peak_flow_gpm']:.1f} GPM | "
                      f"Time: {result['transfer_time_min']:.1f} min | "
                      f"Avg: {result['avg_flow_gpm']:.1f} GPM")
            else:
                print(f"FAILED ({elapsed:.0f}s)")

        # Save results
        if rows:
            df = pd.DataFrame(rows)
            csv_path = os.path.join(RESULTS_DIR, f'{sweep_name}.csv')
            df.to_csv(csv_path, index=False)
            print(f"\n  ✓ Saved {len(rows)} results to {csv_path}")

    # Clean up any leftover sweep run dirs
    import glob as _g
    for d in _g.glob(os.path.join(WORK, 'data', 'runs', '*swp_*')):
        shutil.rmtree(d, ignore_errors=True)

    print(f"\n{'='*70}")
    print(f"  ALL SWEEPS COMPLETE — results in {RESULTS_DIR}/")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
