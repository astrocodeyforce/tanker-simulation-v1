#!/usr/bin/env bash
set -euo pipefail
#
# Sweep F — Liquid Viscosity
# 50 runs: 1 cP → 2000 cP (logarithmic spacing)
# Fixed: 6000 gal, 19 SCFM, 3" hose, density 1340 kg/m³ (SG 1.34)
#
# Usage:  bash scripts/run_viscosity_sweep.sh
#

PROJECT_DIR="/opt/sim-lab/truck-tanker-sim-env"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
RESULTS_DIR="$PROJECT_DIR/data/parametric_sweeps"
mkdir -p "$RESULTS_DIR"

CSV="$RESULTS_DIR/F_viscosity.csv"

# ── Config writer (with viscosity + density params) ──
write_visc_config() {
    local out_path="$1"
    local visc_cP="$2"
    local density="$3"

    cat > "$out_path" <<YAML
scenario_name: "visc_sweep"
tank_total_volume_gal: 7000
tank_diameter_in: 75.0
tank_length_ft: 30.5
initial_liquid_volume_gal: 6000
initial_tank_pressure_psig: 0.0
gas_temperature_C: 25.0
ambient_pressure_psia: 14.696
max_tank_pressure_psig: 25.0
relief_valve_pressure_psig: 27.5
relief_valve_Cd: 0.62
relief_valve_diameter_in: 1.0
air_supply_scfm: 19.0
liquid_density_kg_m3: $density
liquid_viscosity_cP: $visc_cP
valve_diameter_in: 3.0
valve_K_open: 0.2
valve_opening_fraction: 1.0
pipe1_diameter_in: 3.0
pipe1_length_ft: 25.0
pipe1_roughness_mm: 0.01
pipe1_K_minor: 1.5
pipe2_diameter_in: 3.0
pipe2_length_ft: 25.0
pipe2_roughness_mm: 0.01
pipe2_K_minor: 1.0
elevation_change_ft: 0.0
receiver_pressure_psig: 0.0
stop_time_s: 7200
output_interval_s: 1.0
min_liquid_volume_gal: 10.0
YAML
}

# ── Run one simulation and extract metrics ──
run_one() {
    local cfg="$1"
    docker compose --project-directory "$PROJECT_DIR" \
        -f "$COMPOSE_FILE" --project-name simlab \
        run --rm --entrypoint "" openmodelica-runner \
        bash /work/scripts/run_scenario_v2.sh "/work/$cfg" 2>&1 | tail -3
}

extract_metrics() {
    docker exec simlab-dashboard python3 -c "
import pandas as pd, glob, sys
files = sorted(glob.glob('/work/data/runs/*visc_sweep*/outputs.csv'))
if not files:
    print('ERR: no CSV'); sys.exit(1)
df = pd.read_csv(files[-1])

t = df['time']
q = df['Q_L_gpm']
p = df['P_tank_psig']
V_gal = df['V_liquid_gal']

# Transfer time — when liquid drops to near minimum
V0 = V_gal.iloc[0]; V_end = V_gal.iloc[-1]
thresh = V_end + 0.01 * (V0 - V_end)
mask = V_gal <= thresh
if mask.any():
    t_end = t[mask].iloc[0] / 60.0
else:
    t_end = t.iloc[-1] / 60.0

transferred = V0 - V_end
peak_flow = q.max()
peak_pressure = p.max()
avg_flow = transferred / t_end if t_end > 0 else 0

# Time to peak flow
t_peak = t[q == q.max()].iloc[0] / 60.0

# Flow and pressure at 1 min
idx_1m = (t - 60).abs().idxmin()
flow_1m = q[idx_1m]
press_1m = p[idx_1m]

print(f'{peak_flow:.2f},{peak_pressure:.2f},{transferred:.1f},{t_end:.2f},{avg_flow:.2f},{t_peak:.2f},{flow_1m:.2f},{press_1m:.2f}')
" 2>/dev/null
}

# ── Generate 50 logarithmically-spaced viscosity values from 1 to 2000 cP ──
# Using log spacing: 10^(log10(1) + i*(log10(2000)-log10(1))/49)
VISCOSITIES=$(python3 -c "
import math
n = 50
low, high = 1.0, 2000.0
for i in range(n):
    v = 10 ** (math.log10(low) + i * (math.log10(high) - math.log10(low)) / (n-1))
    print(f'{v:.2f}')
")

DENSITY="1340.0"

echo "════════════════════════════════════════════════════════════════"
echo "  SWEEP F — LIQUID VISCOSITY"
echo "  50 runs: 1.00 → 2000.00 cP (log spacing)"
echo "  Fixed: 6000 gal, 19 SCFM, 3\" hose, SG 1.34 (${DENSITY} kg/m³)"
echo "════════════════════════════════════════════════════════════════"

# CSV header
echo "viscosity_cP,peak_flow_gpm,peak_pressure_psig,total_transferred_gal,transfer_time_min,avg_flow_gpm,t_peak_flow_min,flow_at_1min_gpm,pressure_at_1min_psig" > "$CSV"

CFG="config/swpF_test.yaml"
i=0
total=50
for VISC in $VISCOSITIES; do
    i=$((i+1))
    echo ""
    echo "── Run $i/$total: viscosity = ${VISC} cP ──"

    write_visc_config "$CFG" "$VISC" "$DENSITY"
    run_one "$CFG"

    METRICS=$(extract_metrics)
    if [[ -z "$METRICS" || "$METRICS" == ERR* ]]; then
        echo "  ⚠ FAILED to extract metrics"
        echo "$VISC,ERR,ERR,ERR,ERR,ERR,ERR,ERR,ERR" >> "$CSV"
    else
        echo "$VISC,$METRICS" >> "$CSV"
        IFS=',' read -r pf pp tt tm af tp f1 p1 <<< "$METRICS"
        echo "  ✓ Peak: ${pf} GPM | Time: ${tm} min | Avg: ${af} GPM"
    fi
done

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  SWEEP F COMPLETE — $total simulations"
echo "  Results: $CSV"
echo "════════════════════════════════════════════════════════════════"
cat "$CSV" | column -t -s','

