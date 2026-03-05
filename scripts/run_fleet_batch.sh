#!/bin/bash
###############################################################################
# run_fleet_batch.sh — Run all fleet commodity simulations in sequence
###############################################################################
set -euo pipefail

cd /opt/sim-lab/truck-tanker-sim-env

echo "============================================"
echo " Fleet Commodity Batch Simulation"
echo " $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "============================================"

# Step 1: Generate YAML configs
echo ""
echo "--- Generating configs ---"
python3 scripts/fleet_batch_sim.py

MANIFEST="config/fleet_batch_manifest.txt"
if [ ! -f "$MANIFEST" ]; then
    echo "ERROR: Manifest not found"
    exit 1
fi

TOTAL=$(wc -l < "$MANIFEST")
echo ""
echo "--- Running $TOTAL simulations ---"
echo ""

IDX=0
PASSED=0
FAILED=0
RESULTS_LOG="data/fleet_batch_results.txt"
> "$RESULTS_LOG"

while IFS='|' read -r yaml_file name loads cP sg vol; do
    IDX=$((IDX + 1))
    echo "[$IDX/$TOTAL] $name (${cP} cP, SG=${sg}, ${vol} gal) ..."

    CONFIG_PATH="/work/config/${yaml_file}"

    START_TS=$(date +%s)
    if docker compose --project-directory . -f docker-compose.yml --project-name simlab \
        run --rm -T --entrypoint "" openmodelica-runner \
        bash /work/scripts/run_scenario_v2.sh "$CONFIG_PATH" </dev/null 2>&1 | tail -5; then
        END_TS=$(date +%s)
        ELAPSED=$((END_TS - START_TS))
        echo "  ✓ Done in ${ELAPSED}s"
        echo "PASS|$name|$loads|$cP|$sg|$vol|${ELAPSED}s" >> "$RESULTS_LOG"
        PASSED=$((PASSED + 1))
    else
        END_TS=$(date +%s)
        ELAPSED=$((END_TS - START_TS))
        echo "  ✗ FAILED after ${ELAPSED}s"
        echo "FAIL|$name|$loads|$cP|$sg|$vol|${ELAPSED}s" >> "$RESULTS_LOG"
        FAILED=$((FAILED + 1))
    fi
    echo ""
done < "$MANIFEST"

echo "============================================"
echo " Batch Complete: $PASSED passed, $FAILED failed out of $TOTAL"
echo " Results log: $RESULTS_LOG"
echo "============================================"
