#!/usr/bin/env bash
set -euo pipefail
#
# HOSE DIAMETER SWEEP — Multi-dimensional
# 4 diameters × 5 volumes × 5 compressor sizes = 100 simulations
#
# Diameters: 2", 3", 4", 5"
# Volumes:   4000, 4500, 5000, 5500, 6000 gal
# SCFM:      15, 19, 25, 35, 50
#

PROJECT_DIR="/opt/sim-lab/truck-tanker-sim-env"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
RESULTS_DIR="$PROJECT_DIR/data/parametric_sweeps"
mkdir -p "$RESULTS_DIR"

DIAMETERS="2 3 4 5"
VOLUMES="4000 4500 5000 5500 6000"
SCFMS="15 19 25 35 50"

CSV_OUT="$RESULTS_DIR/E_hose_diameter_multi.csv"
echo "hose_diameter_in,liquid_volume_gal,compressor_scfm,peak_flow_gpm,peak_pressure_psig,total_transferred_gal,transfer_time_min,avg_flow_gpm,t_peak_flow_min,flow_at_1min_gpm,pressure_at_1min_psig" > "$CSV_OUT"

write_hose_config() {
    local out_path="$1"
    local scenario="$2"
    local diameter="$3"
    local liquid_vol="$4"
    local scfm="$5"

    cat > "$out_path" <<YAML
scenario_name: "$scenario"
tank_total_volume_gal: 7000
tank_diameter_in: 75.0
tank_length_ft: 30.5
initial_liquid_volume_gal: $liquid_vol
initial_tank_pressure_psig: 0.0
gas_temperature_C: 20.0
ambient_pressure_psia: 14.696
max_tank_pressure_psig: 25.0
relief_valve_pressure_psig: 27.5
relief_valve_Cd: 0.62
relief_valve_diameter_in: 1.0
air_supply_scfm: $scfm
liquid_density_kg_m3: 1050.0
liquid_viscosity_cP: 100.0
valve_diameter_in: $diameter
valve_K_open: 0.2
valve_opening_fraction: 1.0
pipe1_diameter_in: $diameter
pipe1_length_ft: 25.0
pipe1_roughness_mm: 0.01
pipe1_K_minor: 1.5
pipe2_diameter_in: $diameter
pipe2_length_ft: 25.0
pipe2_roughness_mm: 0.01
pipe2_K_minor: 1.0
elevation_change_ft: 0.0
receiver_pressure_psig: 0.0
stop_time_s: 5400
output_interval_s: 1.0
min_liquid_volume_gal: 10.0
YAML
}

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  HOSE DIAMETER MULTI-SWEEP                                 ║"
echo "║  4 diameters × 5 volumes × 5 SCFM = 100 simulations       ║"
echo "║  Diameters: 2\", 3\", 4\", 5\"                                ║"
echo "║  Volumes: 4000, 4500, 5000, 5500, 6000 gal                ║"
echo "║  SCFM: 15, 19, 25, 35, 50                                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

total=100
count=0

for diam in $DIAMETERS; do
    echo "============================================================"
    echo "  HOSE DIAMETER: ${diam}\" — 25 combinations"
    echo "============================================================"

    for vol in $VOLUMES; do
        for scfm in $SCFMS; do
            count=$((count + 1))
            tag="swpE_d${diam}_v${vol}_s${scfm}"
            printf "  [%3d/100] d=%s\" vol=%s scfm=%s ... " "$count" "$diam" "$vol" "$scfm"

            write_hose_config "$PROJECT_DIR/config/${tag}.yaml" "$tag" "$diam" "$vol" "$scfm"

            t0=$(date +%s)

            # Run simulation
            docker compose --project-directory "$PROJECT_DIR" \
                -f "$COMPOSE_FILE" --project-name simlab \
                run --rm --entrypoint "" openmodelica-runner \
                bash /work/scripts/run_scenario_v2.sh "/work/config/${tag}.yaml" \
                > /dev/null 2>&1 || true

            csv_file=$(find "$PROJECT_DIR/data/runs" -path "*${tag}*/outputs.csv" 2>/dev/null | sort | tail -1)
            elapsed=$(( $(date +%s) - t0 ))

            if [[ -z "$csv_file" ]]; then
                echo "FAILED (${elapsed}s)"
                rm -f "$PROJECT_DIR/config/${tag}.yaml"
                continue
            fi

            container_csv="${csv_file/$PROJECT_DIR//work}"
            result=$(docker exec simlab-dashboard python3 -c "
import pandas as pd
df = pd.read_csv('$container_csv')
peak_flow = df['Q_L_gpm'].max()
peak_p = df['P_tank_psig'].max()
xfer = df['V_transferred_gal'].iloc[-1]
low = df[df['Q_L_gpm'] < 1.0]
if len(low) > 0 and low.index[0] > 10:
    t_done = df.loc[low.index[0], 'time'] / 60.0
else:
    t_done = df['time'].iloc[-1] / 60.0
avg = xfer / t_done if t_done > 0 else 0
peak_idx = df['Q_L_gpm'].idxmax()
t_peak = df.loc[peak_idx, 'time'] / 60.0
r60 = df[df['time'] >= 60]
if len(r60) > 0:
    f60 = r60.iloc[0]['Q_L_gpm']
    p60 = r60.iloc[0]['P_tank_psig']
else:
    f60 = 0; p60 = 0
print(f'${diam},${vol},${scfm},{peak_flow:.2f},{peak_p:.2f},{xfer:.1f},{t_done:.2f},{avg:.2f},{t_peak:.2f},{f60:.2f},{p60:.2f}')
" 2>&1) || true

            if [[ -n "$result" ]] && [[ "$result" != *"Error"* ]] && [[ "$result" != *"Traceback"* ]]; then
                echo "$result" >> "$CSV_OUT"
                flow=$(echo "$result" | cut -d',' -f4)
                time=$(echo "$result" | cut -d',' -f7)
                avg=$(echo "$result" | cut -d',' -f8)
                echo "OK ${elapsed}s | Peak: ${flow} GPM | Time: ${time} min | Avg: ${avg} GPM"
            else
                echo "FAILED (${elapsed}s)"
            fi

            # Cleanup
            run_dir=$(dirname "$csv_file")
            rm -rf "$run_dir"
            rm -f "$PROJECT_DIR/config/${tag}.yaml"
        done
    done
    echo ""
done

echo "============================================================"
echo "  ALL DONE — 100 simulations"
echo "  Results: $CSV_OUT"
wc -l "$CSV_OUT"
echo "============================================================"
