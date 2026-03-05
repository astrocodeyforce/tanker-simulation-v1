#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# Vacuum Threshold Sweep — Find min SCFM to prevent vacuum at 0 psig
# Water (1 cP, 998 kg/m³), 3" hose, volumes: 6000 & 6500 gal
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

PROJECT=/opt/sim-lab/truck-tanker-sim-env
SWEEP_DIR="$PROJECT/data/parametric_sweeps"
RESULTS_CSV="$SWEEP_DIR/I_vacuum_threshold.csv"

echo "volume_gal,scfm,min_pressure_psig,peak_flow_gpm,transfer_time_min,vacuum_free" > "$RESULTS_CSV"

VOLUMES="6000 6500"
SCFMS="19 20 21 22 23 24 25 26 27 28 29 30 32 34 36 38 40"
VISCOSITY=1.0
DIAMETER=3
PRESSURE=0

total=0
for v in $VOLUMES; do for s in $SCFMS; do total=$((total+1)); done; done

echo "═══════════════════════════════════════════════════"
echo "  Vacuum Threshold Sweep — $total simulations"
echo "  Water (1 cP), 3\" hose, 0 psig start"
echo "═══════════════════════════════════════════════════"

run=0
for VOL in $VOLUMES; do
  for SCFM in $SCFMS; do
    run=$((run+1))
    TAG="vacI_${VOL}gal_${SCFM}scfm"
    RUN_DIR="$PROJECT/data/runs/$TAG"

    # Clean any previous run
    rm -rf "$RUN_DIR"

    # Generate YAML config
    cat > "$PROJECT/config/sweep_tmp.yaml" << EOF
scenario_name: $TAG
tank_total_volume_gal: 7000
tank_diameter_in: 75
tank_length_ft: 0
initial_liquid_volume_gal: $VOL
initial_tank_pressure_psig: $PRESSURE
gas_temperature_C: 20.0
ambient_pressure_psia: 14.696
max_tank_pressure_psig: 25.0
relief_valve_pressure_psig: 27.5
relief_valve_Cd: 0.62
relief_valve_diameter_in: 1.0
air_supply_scfm: $SCFM
liquid_density_kg_m3: 998.0
liquid_viscosity_cP: $VISCOSITY
valve_diameter_in: $DIAMETER
valve_K_open: 0.2
valve_opening_fraction: 1.0
pipe1_diameter_in: $DIAMETER
pipe1_length_ft: 25.0
pipe1_roughness_mm: 0.01
pipe1_K_minor: 1.5
pipe2_diameter_in: $DIAMETER
pipe2_length_ft: 25.0
pipe2_roughness_mm: 0.01
pipe2_K_minor: 1.0
elevation_change_ft: 0.0
receiver_pressure_psig: 0.0
stop_time_s: 5400
output_interval_s: 1.0
min_liquid_volume_gal: 10.0
EOF

    # Run simulation using openmodelica-runner
    docker compose --project-directory "$PROJECT" \
      -f "$PROJECT/docker-compose.yml" --project-name simlab \
      run --rm --entrypoint "" openmodelica-runner \
      bash /work/scripts/run_scenario_v2.sh /work/config/sweep_tmp.yaml \
      > /dev/null 2>&1

    # Find the output (timestamped dir)
    LATEST=$(ls -dt "$PROJECT"/data/runs/*"$TAG"* 2>/dev/null | head -1)
    if [ -n "$LATEST" ] && [ -f "$LATEST/outputs.csv" ]; then
      # Rename to clean tag
      if [ "$LATEST" != "$RUN_DIR" ]; then
        rm -rf "$RUN_DIR"
        mv "$LATEST" "$RUN_DIR"
      fi

      RESULTS=$(awk -F, '
        NR==1 {next}
        {
          p=$2+0; q=$6+0
          if(NR==2 || p<min_p) min_p=p
          if(NR==2 || q>max_q) max_q=q
          if(q>0) last_t=$1+0
        }
        END {
          printf "%.4f,%.1f,%.1f", min_p, max_q, last_t/60
        }
      ' "$RUN_DIR/outputs.csv")

      MIN_P=$(echo "$RESULTS" | cut -d, -f1)
      PEAK_Q=$(echo "$RESULTS" | cut -d, -f2)
      TIME_M=$(echo "$RESULTS" | cut -d, -f3)

      VACUUM_FREE=$(awk "BEGIN{print ($MIN_P >= -0.01) ? \"YES\" : \"NO\"}")

      echo "$VOL,$SCFM,$MIN_P,$PEAK_Q,$TIME_M,$VACUUM_FREE" >> "$RESULTS_CSV"

      if [ "$VACUUM_FREE" = "YES" ]; then
        echo "  [$run/$total] ${VOL}gal ${SCFM}SCFM → min_P=${MIN_P} psig  Q=${PEAK_Q}GPM  t=${TIME_M}min  ✅ NO VACUUM"
      else
        echo "  [$run/$total] ${VOL}gal ${SCFM}SCFM → min_P=${MIN_P} psig  Q=${PEAK_Q}GPM  t=${TIME_M}min  ❌ VACUUM"
      fi
    else
      echo "  [$run/$total] FAIL $TAG"
      echo "$VOL,$SCFM,FAIL,FAIL,FAIL,FAIL" >> "$RESULTS_CSV"
    fi
  done
done

echo ""
echo "═══════════════════════════════════════════════════"
echo "  COMPLETE — Results saved to $RESULTS_CSV"
echo "═══════════════════════════════════════════════════"
column -t -s, "$RESULTS_CSV"
