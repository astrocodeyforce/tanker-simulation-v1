#!/usr/bin/env bash
set -euo pipefail
#
# SWEEP H — MEGA 4-DIMENSIONAL COMBINATION SWEEP
# ════════════════════════════════════════════════════════════════
# Variables: Viscosity × Compressor × Hose Diameter × Volume × Pressure
#   6 viscosities × 5 SCFM × 3 diameters × 4 volumes × 3 pressures = 1080 sims
#
# Fixed: SG 1.34 (1340 kg/m³), 25°C, tank 7000 gal total
#
# For each run with pressure > 0 psig:
#   1. The simulation runs with that initial pressure → gives valve_transfer_time
#   2. We calculate pre-pressurization time analytically:
#      - Headspace volume = V_tank(7000 gal) - V_liquid (in SCF)
#      - Air needed = V_headspace_SCF × (P_target_psig / 14.696)
#      - Pressurize time = Air_needed / SCFM
#   3. Total time = pressurize_time + valve_transfer_time
#

PROJECT_DIR="/opt/sim-lab/truck-tanker-sim-env"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
RESULTS_DIR="$PROJECT_DIR/data/parametric_sweeps"
mkdir -p "$RESULTS_DIR"

CSV="$RESULTS_DIR/H_mega_combo.csv"

# ── Grid values ──
VISCOSITIES="1 10 100 500 1000 2000"
SCFMS="19 25 35 50 64"
DIAMETERS="3 4 5"
VOLUMES="4000 5000 6000 6500"
PRESSURES="0 10 22"

DENSITY="1340.0"
TANK_TOTAL_GAL="7000"

# ── Constants for pressurization time calc ──
GAL_TO_CF="0.133681"  # 1 US gallon = 0.133681 cubic feet
ATM_PSIA="14.696"

# Count total
total=0
for v in $VISCOSITIES; do for s in $SCFMS; do for d in $DIAMETERS; do
for vol in $VOLUMES; do for p in $PRESSURES; do
    total=$((total+1))
done; done; done; done; done

calc_pressurize_time() {
    # Calculate time (minutes) to pressurize headspace
    # Args: $1=liquid_vol_gal $2=pressure_psig $3=scfm
    local liq_gal="$1"
    local psi="$2"
    local scfm="$3"

    if [[ "$psi" == "0" ]]; then
        echo "0.00"
        return
    fi

    # Headspace in gallons, then SCF
    # Air needed at standard conditions: V_headspace_SCF × (P_psig / 14.696)
    # Time = air_SCF / SCFM  (in minutes)
    python3 -c "
headspace_gal = $TANK_TOTAL_GAL - $liq_gal
headspace_scf = headspace_gal * $GAL_TO_CF
air_needed_scf = headspace_scf * ($psi / $ATM_PSIA)
t_min = air_needed_scf / $scfm
print(f'{t_min:.2f}')
"
}

write_mega_config() {
    local out_path="$1"
    local visc_cP="$2"
    local scfm="$3"
    local diameter="$4"
    local volume="$5"
    local pressure="$6"

    cat > "$out_path" <<YAML
scenario_name: "mega_sweep"
tank_total_volume_gal: $TANK_TOTAL_GAL
tank_diameter_in: 75.0
tank_length_ft: 0
initial_liquid_volume_gal: $volume
initial_tank_pressure_psig: ${pressure}.0
gas_temperature_C: 25.0
ambient_pressure_psia: 14.696
max_tank_pressure_psig: 25.0
relief_valve_pressure_psig: 27.5
relief_valve_Cd: 0.62
relief_valve_diameter_in: 1.0
air_supply_scfm: $scfm
liquid_density_kg_m3: $DENSITY
liquid_viscosity_cP: $visc_cP
valve_diameter_in: ${diameter}.0
valve_K_open: 0.2
valve_opening_fraction: 1.0
pipe1_diameter_in: ${diameter}.0
pipe1_length_ft: 25.0
pipe1_roughness_mm: 0.01
pipe1_K_minor: 1.5
pipe2_diameter_in: ${diameter}.0
pipe2_length_ft: 25.0
pipe2_roughness_mm: 0.01
pipe2_K_minor: 1.0
elevation_change_ft: 0.0
receiver_pressure_psig: 0.0
stop_time_s: 9000
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
files = sorted(glob.glob('/work/data/runs/*mega_sweep*/outputs.csv'))
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

START_TIME=$(date +%s)

echo "════════════════════════════════════════════════════════════════════════"
echo "  SWEEP H — MEGA 4D COMBINATION SWEEP"
echo "  6 visc × 5 SCFM × 3 diam × 4 vol × 3 press = $total simulations"
echo "  Fixed: SG 1.34 (1340 kg/m³), 25°C, 7000 gal tank"
echo "  Tank starts EMPTY (just gas) → pressurize → then transfer"
echo "════════════════════════════════════════════════════════════════════════"

echo "viscosity_cP,compressor_scfm,hose_diameter_in,liquid_volume_gal,initial_pressure_psig,pressurize_time_min,valve_transfer_time_min,total_time_min,peak_flow_gpm,peak_pressure_psig,total_transferred_gal,avg_flow_gpm,t_peak_flow_min,flow_at_1min_gpm,pressure_at_1min_psig" > "$CSV"

CFG="config/swpH_test.yaml"
i=0
pass=0
fail=0

for VISC in $VISCOSITIES; do
  for SCFM in $SCFMS; do
    for DIAM in $DIAMETERS; do
      for VOL in $VOLUMES; do
        for PRESS in $PRESSURES; do
            i=$((i+1))

            # Elapsed time
            NOW=$(date +%s)
            ELAPSED=$(( NOW - START_TIME ))
            ELAPSED_M=$(( ELAPSED / 60 ))

            # ETA
            if [[ $i -gt 1 ]]; then
                AVG_SEC=$(( ELAPSED / (i - 1) ))
                REMAIN=$(( (total - i + 1) * AVG_SEC ))
                ETA_M=$(( REMAIN / 60 ))
            else
                ETA_M="?"
            fi

            echo ""
            echo "── Run $i/$total [${ELAPSED_M}m elapsed, ~${ETA_M}m remain] ──"
            echo "   ${VISC}cP | ${SCFM}SCFM | ${DIAM}\" | ${VOL}gal | ${PRESS}psig"

            # Calculate pre-pressurization time
            PRESS_TIME=$(calc_pressurize_time "$VOL" "$PRESS" "$SCFM")

            write_mega_config "$CFG" "$VISC" "$SCFM" "$DIAM" "$VOL" "$PRESS"

            # Clear old run data
            rm -rf "$PROJECT_DIR/data/runs/"*mega_sweep* 2>/dev/null || true

            run_one "$CFG"

            METRICS=$(extract_metrics)
            if [[ -z "$METRICS" || "$METRICS" == ERR* ]]; then
                echo "  ⚠ FAILED"
                echo "$VISC,$SCFM,$DIAM,$VOL,$PRESS,$PRESS_TIME,ERR,ERR,ERR,ERR,ERR,ERR,ERR,ERR,ERR" >> "$CSV"
                fail=$((fail+1))
            else
                IFS=',' read -r pf pp tt tm af tp f1 p1 <<< "$METRICS"
                # Total time = pressurization + valve transfer
                TOTAL_TIME=$(python3 -c "print(f'{$PRESS_TIME + $tm:.2f}')")
                echo "$VISC,$SCFM,$DIAM,$VOL,$PRESS,$PRESS_TIME,$tm,$TOTAL_TIME,$pf,$pp,$tt,$af,$tp,$f1,$p1" >> "$CSV"
                echo "  ✓ Press: ${PRESS_TIME}m + Valve: ${tm}m = Total: ${TOTAL_TIME}m | Peak: ${pf} GPM"
                pass=$((pass+1))
            fi
        done
      done
    done
  done
done

END_TIME=$(date +%s)
TOTAL_ELAPSED=$(( (END_TIME - START_TIME) / 60 ))

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "  SWEEP H COMPLETE — $total simulations in ${TOTAL_ELAPSED} minutes"
echo "  Passed: $pass | Failed: $fail"
echo "  Results: $CSV"
echo "════════════════════════════════════════════════════════════════════════"
