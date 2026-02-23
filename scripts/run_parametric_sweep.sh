#!/usr/bin/env bash
set -euo pipefail
#
# Parametric Sweep — runs directly on HOST (no Docker-in-Docker issues)
# 3 sweeps × 50 sims = 150 total
#
# Usage:  bash scripts/run_parametric_sweep.sh [A|B|C|ALL]
#

PROJECT_DIR="/opt/sim-lab/truck-tanker-sim-env"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
RESULTS_DIR="$PROJECT_DIR/data/parametric_sweeps"
mkdir -p "$RESULTS_DIR"

WHICH="${1:-ALL}"

# ── Base config template ──
write_config() {
    local out_path="$1"
    local scenario="$2"
    local liquid_vol="$3"
    local tank_pressure="$4"
    local gas_temp="$5"
    local scfm="${6:-19.0}"

    cat > "$out_path" <<YAML
scenario_name: "$scenario"
tank_total_volume_gal: 7000
tank_diameter_in: 75.0
tank_length_ft: 30.5
initial_liquid_volume_gal: $liquid_vol
initial_tank_pressure_psig: $tank_pressure
gas_temperature_C: $gas_temp
ambient_pressure_psia: 14.696
max_tank_pressure_psig: 25.0
relief_valve_pressure_psig: 27.5
relief_valve_Cd: 0.62
relief_valve_diameter_in: 1.0
air_supply_scfm: $scfm
liquid_density_kg_m3: 1050.0
liquid_viscosity_cP: 100.0
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
stop_time_s: 5400
output_interval_s: 1.0
min_liquid_volume_gal: 10.0
YAML
}

# ── Run one simulation and extract metrics ──
run_one() {
    local cfg_path="$1"
    local tag="$2"
    local param_val="$3"
    local csv_header="$4"  # "liquid_gal" or "pressure_psig" or "temp_C"

    # Run simulation
    docker compose --project-directory "$PROJECT_DIR" \
        -f "$COMPOSE_FILE" --project-name simlab \
        run --rm --entrypoint "" openmodelica-runner \
        bash /work/scripts/run_scenario_v2.sh "/work/config/${tag}.yaml" \
        > /dev/null 2>&1

    # Find output CSV
    local csv_file
    csv_file=$(find "$PROJECT_DIR/data/runs" -path "*${tag}*/outputs.csv" 2>/dev/null | sort | tail -1)

    if [[ -z "$csv_file" ]]; then
        echo "FAILED"
        return 1
    fi

    # Extract metrics with Python inside dashboard container (has pandas)
    # Convert host path to container path: /opt/sim-lab/truck-tanker-sim-env/... -> /work/...
    local container_csv="${csv_file/$PROJECT_DIR//work}"
    docker exec simlab-dashboard python3 -c "
import pandas as pd, sys
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
print(f'$param_val,{peak_flow:.2f},{peak_p:.2f},{xfer:.1f},{t_done:.2f},{avg:.2f},{t_peak:.2f},{f60:.2f},{p60:.2f}')
"
    # Cleanup run directory
    local run_dir
    run_dir=$(dirname "$csv_file")
    rm -rf "$run_dir"
    rm -f "$PROJECT_DIR/config/${tag}.yaml"
}


# ══════════════════════════════════════════════════════════════
#  SWEEP A: Liquid Volume — 4000 to 6500 gal, 50 points
# ══════════════════════════════════════════════════════════════
run_sweep_A() {
    echo "============================================================"
    echo "  SWEEP A: Liquid Volume — 4000 to 6500 gal (50 sims)"
    echo "============================================================"

    local csv_out="$RESULTS_DIR/A_liquid_volume.csv"
    echo "initial_liquid_volume_gal,peak_flow_gpm,peak_pressure_psig,total_transferred_gal,transfer_time_min,avg_flow_gpm,t_peak_flow_min,flow_at_1min_gpm,pressure_at_1min_psig" > "$csv_out"

    # Generate 50 values from 4000 to 6500
    local values
    values=$(python3 -c "[print(f'{4000 + i * (6500-4000)/49:.2f}') for i in range(50)]")

    local i=0
    for val in $values; do
        i=$((i + 1))
        local tag="swpA_$(printf '%03d' $i)"
        printf "  [%2d/50] Liquid = %s gal ... " "$i" "$val"

        write_config "$PROJECT_DIR/config/${tag}.yaml" "$tag" "$val" "0.0" "20.0"

        local t0
        t0=$(date +%s)
        local result
        result=$(run_one "$PROJECT_DIR/config/${tag}.yaml" "$tag" "$val" "liquid_gal" 2>&1) || true
        local elapsed=$(( $(date +%s) - t0 ))

        if [[ "$result" == "FAILED" ]] || [[ -z "$result" ]]; then
            echo "FAILED (${elapsed}s)"
        else
            echo "$result" >> "$csv_out"
            # Parse for display
            local flow time avg
            flow=$(echo "$result" | cut -d',' -f2)
            time=$(echo "$result" | cut -d',' -f5)
            avg=$(echo "$result" | cut -d',' -f6)
            echo "OK ${elapsed}s | Peak: ${flow} GPM | Time: ${time} min | Avg: ${avg} GPM"
        fi
    done

    echo ""
    echo "  ✓ Sweep A saved to $csv_out"
    echo ""
}


# ══════════════════════════════════════════════════════════════
#  SWEEP B: Tank Pressure — 0.0 to 24.5 psig, step 0.5
# ══════════════════════════════════════════════════════════════
run_sweep_B() {
    echo "============================================================"
    echo "  SWEEP B: Tank Pressure — 0.0 to 24.5 psig (50 sims)"
    echo "============================================================"

    local csv_out="$RESULTS_DIR/B_tank_pressure.csv"
    echo "initial_tank_pressure_psig,peak_flow_gpm,peak_pressure_psig,total_transferred_gal,transfer_time_min,avg_flow_gpm,t_peak_flow_min,flow_at_1min_gpm,pressure_at_1min_psig" > "$csv_out"

    local i=0
    for n in $(seq 0 49); do
        i=$((i + 1))
        local val
        val=$(python3 -c "print(f'{$n * 0.5:.1f}')")
        local tag="swpB_$(printf '%03d' $i)"
        printf "  [%2d/50] Pressure = %s psig ... " "$i" "$val"

        write_config "$PROJECT_DIR/config/${tag}.yaml" "$tag" "6500" "$val" "20.0"

        local t0
        t0=$(date +%s)
        local result
        result=$(run_one "$PROJECT_DIR/config/${tag}.yaml" "$tag" "$val" "pressure_psig" 2>&1) || true
        local elapsed=$(( $(date +%s) - t0 ))

        if [[ "$result" == "FAILED" ]] || [[ -z "$result" ]]; then
            echo "FAILED (${elapsed}s)"
        else
            echo "$result" >> "$csv_out"
            local flow time avg
            flow=$(echo "$result" | cut -d',' -f2)
            time=$(echo "$result" | cut -d',' -f5)
            avg=$(echo "$result" | cut -d',' -f6)
            echo "OK ${elapsed}s | Peak: ${flow} GPM | Time: ${time} min | Avg: ${avg} GPM"
        fi
    done

    echo ""
    echo "  ✓ Sweep B saved to $csv_out"
    echo ""
}


# ══════════════════════════════════════════════════════════════
#  SWEEP C: Gas Temperature — 15 to 40 °C, 50 points
# ══════════════════════════════════════════════════════════════
run_sweep_C() {
    echo "============================================================"
    echo "  SWEEP C: Gas Temperature — 15 to 40 °C (50 sims)"
    echo "============================================================"

    local csv_out="$RESULTS_DIR/C_gas_temperature.csv"
    echo "gas_temperature_C,peak_flow_gpm,peak_pressure_psig,total_transferred_gal,transfer_time_min,avg_flow_gpm,t_peak_flow_min,flow_at_1min_gpm,pressure_at_1min_psig" > "$csv_out"

    local values
    values=$(python3 -c "[print(f'{15 + i * (40-15)/49:.2f}') for i in range(50)]")

    local i=0
    for val in $values; do
        i=$((i + 1))
        local tag="swpC_$(printf '%03d' $i)"
        printf "  [%2d/50] Temp = %s °C ... " "$i" "$val"

        write_config "$PROJECT_DIR/config/${tag}.yaml" "$tag" "6500" "0.0" "$val"

        local t0
        t0=$(date +%s)
        local result
        result=$(run_one "$PROJECT_DIR/config/${tag}.yaml" "$tag" "$val" "temp_C" 2>&1) || true
        local elapsed=$(( $(date +%s) - t0 ))

        if [[ "$result" == "FAILED" ]] || [[ -z "$result" ]]; then
            echo "FAILED (${elapsed}s)"
        else
            echo "$result" >> "$csv_out"
            local flow time avg
            flow=$(echo "$result" | cut -d',' -f2)
            time=$(echo "$result" | cut -d',' -f5)
            avg=$(echo "$result" | cut -d',' -f6)
            echo "OK ${elapsed}s | Peak: ${flow} GPM | Time: ${time} min | Avg: ${avg} GPM"
        fi
    done

    echo ""
    echo "  ✓ Sweep C saved to $csv_out"
    echo ""
}


# ══════════════════════════════════════════════════════════════
#  SWEEP D: Compressor SCFM — 15 to 64 SCFM, step 1 (50 sims)
#  Base: 6000 gal, 0 psig, 20°C, Latex 100 cP
# ══════════════════════════════════════════════════════════════
run_sweep_D() {
    echo "============================================================"
    echo "  SWEEP D: Compressor SCFM — 15 to 64 SCFM (50 sims)"
    echo "  Base: 6000 gal, 0 psig, 20°C, Latex 100 cP"
    echo "============================================================"

    local csv_out="$RESULTS_DIR/D_compressor_scfm.csv"
    echo "air_supply_scfm,peak_flow_gpm,peak_pressure_psig,total_transferred_gal,transfer_time_min,avg_flow_gpm,t_peak_flow_min,flow_at_1min_gpm,pressure_at_1min_psig" > "$csv_out"

    local i=0
    for n in $(seq 0 49); do
        i=$((i + 1))
        local val=$((15 + n))
        local tag="swpD_$(printf '%03d' $i)"
        printf "  [%2d/50] SCFM = %d ... " "$i" "$val"

        write_config "$PROJECT_DIR/config/${tag}.yaml" "$tag" "6000" "0.0" "20.0" "$val"

        local t0
        t0=$(date +%s)
        local result
        result=$(run_one "$PROJECT_DIR/config/${tag}.yaml" "$tag" "$val" "scfm" 2>&1) || true
        local elapsed=$(( $(date +%s) - t0 ))

        if [[ "$result" == "FAILED" ]] || [[ -z "$result" ]]; then
            echo "FAILED (${elapsed}s)"
        else
            echo "$result" >> "$csv_out"
            local flow time avg
            flow=$(echo "$result" | cut -d',' -f2)
            time=$(echo "$result" | cut -d',' -f5)
            avg=$(echo "$result" | cut -d',' -f6)
            echo "OK ${elapsed}s | Peak: ${flow} GPM | Time: ${time} min | Avg: ${avg} GPM"
        fi
    done

    echo ""
    echo "  ✓ Sweep D saved to $csv_out"
    echo ""
}


# ── Main ──
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  PARAMETRIC SWEEP — 3 Variables × 50 Simulations Each      ║"
echo "║  Base: Latex 1050 kg/m³, 100 cP, 19 SCFM, 3\" pipe         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

[[ "$WHICH" == "ALL" || "$WHICH" == "A" ]] && run_sweep_A
[[ "$WHICH" == "ALL" || "$WHICH" == "B" ]] && run_sweep_B
[[ "$WHICH" == "ALL" || "$WHICH" == "C" ]] && run_sweep_C
[[ "$WHICH" == "ALL" || "$WHICH" == "D" ]] && run_sweep_D

echo "============================================================"
echo "  ALL DONE — Results saved in $RESULTS_DIR/"
ls -la "$RESULTS_DIR/"*.csv 2>/dev/null
echo "============================================================"
