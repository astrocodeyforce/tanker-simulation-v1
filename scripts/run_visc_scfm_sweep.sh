#!/usr/bin/env bash
set -euo pipefail
#
# Sweep G — Viscosity × Compressor SCFM (multi-dimensional)
# 10 viscosities × 10 compressor sizes = 100 simulations
# Fixed: 6000 gal, SG 1.34 (1340 kg/m³), 3" hose, 0 psig, 25°C
#

PROJECT_DIR="/opt/sim-lab/truck-tanker-sim-env"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
RESULTS_DIR="$PROJECT_DIR/data/parametric_sweeps"
mkdir -p "$RESULTS_DIR"

CSV="$RESULTS_DIR/G_visc_scfm_combo.csv"

VISCOSITIES="1 2 5 10 50 100 200 500 1000 2000"
SCFMS="15 17 19 22 25 30 35 40 50 64"
DENSITY="1340.0"

# Count total
total=0
for v in $VISCOSITIES; do for s in $SCFMS; do total=$((total+1)); done; done

write_combo_config() {
    local out_path="$1"
    local visc_cP="$2"
    local scfm="$3"

    cat > "$out_path" <<YAML
scenario_name: "vscfm_sweep"
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
air_supply_scfm: $scfm
liquid_density_kg_m3: $DENSITY
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
files = sorted(glob.glob('/work/data/runs/*vscfm_sweep*/outputs.csv'))
if not files:
    print('ERR: no CSV'); sys.exit(1)
df = pd.read_csv(files[-1])
t = df['time']; q = df['Q_L_gpm']; p = df['P_tank_psig']; V_gal = df['V_liquid_gal']
V0 = V_gal.iloc[0]; V_end = V_gal.iloc[-1]
thresh = V_end + 0.01 * (V0 - V_end)
mask = V_gal <= thresh
t_end = t[mask].iloc[0] / 60.0 if mask.any() else t.iloc[-1] / 60.0
transferred = V0 - V_end
peak_flow = q.max()
peak_pressure = p.max()
avg_flow = transferred / t_end if t_end > 0 else 0
t_peak = t[q == q.max()].iloc[0] / 60.0
idx_1m = (t - 60).abs().idxmin()
flow_1m = q[idx_1m]; press_1m = p[idx_1m]
print(f'{peak_flow:.2f},{peak_pressure:.2f},{transferred:.1f},{t_end:.2f},{avg_flow:.2f},{t_peak:.2f},{flow_1m:.2f},{press_1m:.2f}')
" 2>/dev/null
}

echo "════════════════════════════════════════════════════════════════"
echo "  SWEEP G — VISCOSITY × COMPRESSOR SCFM"
echo "  10 viscosities × 10 SCFM = $total simulations"
echo "  Fixed: 6000 gal, SG 1.34, 3\" hose"
echo "════════════════════════════════════════════════════════════════"

echo "viscosity_cP,compressor_scfm,peak_flow_gpm,peak_pressure_psig,total_transferred_gal,transfer_time_min,avg_flow_gpm,t_peak_flow_min,flow_at_1min_gpm,pressure_at_1min_psig" > "$CSV"

CFG="config/swpG_test.yaml"
i=0
for VISC in $VISCOSITIES; do
    for SCFM in $SCFMS; do
        i=$((i+1))
        echo ""
        echo "── Run $i/$total: ${VISC} cP × ${SCFM} SCFM ──"

        write_combo_config "$CFG" "$VISC" "$SCFM"
        run_one "$CFG"

        METRICS=$(extract_metrics)
        if [[ -z "$METRICS" || "$METRICS" == ERR* ]]; then
            echo "  ⚠ FAILED"
            echo "$VISC,$SCFM,ERR,ERR,ERR,ERR,ERR,ERR,ERR,ERR" >> "$CSV"
        else
            echo "$VISC,$SCFM,$METRICS" >> "$CSV"
            IFS=',' read -r pf pp tt tm af tp f1 p1 <<< "$METRICS"
            echo "  ✓ Peak: ${pf} GPM | Time: ${tm} min | Avg: ${af} GPM"
        fi
    done
done

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  SWEEP G COMPLETE — $total simulations"
echo "  Results: $CSV"
echo "════════════════════════════════════════════════════════════════"
