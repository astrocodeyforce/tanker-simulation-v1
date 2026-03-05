#!/bin/bash
###############################################################################
# run_six_studies.sh — Run all 6 simulation studies sequentially
#
# Reads studies_manifest.txt and runs each config through the simulator.
# Can filter by study: ./run_six_studies.sh study1
# Or run all:          ./run_six_studies.sh
###############################################################################

set -euo pipefail

BASE_DIR="/opt/sim-lab/truck-tanker-sim-env"
MANIFEST="${BASE_DIR}/config/studies/studies_manifest.txt"
RESULTS_LOG="${BASE_DIR}/data/six_studies_results.txt"
STUDY_FILTER="${1:-all}"

if [ ! -f "$MANIFEST" ]; then
    echo "ERROR: Manifest not found: $MANIFEST"
    exit 1
fi

# Count total sims
if [ "$STUDY_FILTER" = "all" ]; then
    TOTAL=$(wc -l < "$MANIFEST")
else
    TOTAL=$(grep "^${STUDY_FILTER}|" "$MANIFEST" | wc -l)
fi

echo "============================================"
echo " Six Studies Batch Runner"
echo " Filter: $STUDY_FILTER"
echo " Total simulations: $TOTAL"
echo " Started: $(date)"
echo "============================================"

PASS=0
FAIL=0
COUNT=0

# Clear/create results log
> "$RESULTS_LOG"

while IFS='|' read -r study scenario yaml_file meta; do
    # Filter by study if specified
    if [ "$STUDY_FILTER" != "all" ] && [ "$study" != "$STUDY_FILTER" ]; then
        continue
    fi

    COUNT=$((COUNT + 1))
    CONFIG_PATH="/work/config/studies/${yaml_file}"
    
    echo ""
    echo "[${COUNT}/${TOTAL}] ${study}: ${scenario}"
    
    START_SEC=$(date +%s)
    
    if docker compose run --rm -T --entrypoint "" openmodelica-runner \
        bash /work/scripts/run_scenario_v2.sh "$CONFIG_PATH" </dev/null 2>&1 | tail -3; then
        END_SEC=$(date +%s)
        ELAPSED=$((END_SEC - START_SEC))
        echo "  ✓ Done in ${ELAPSED}s"
        echo "PASS|${study}|${scenario}|${ELAPSED}s" >> "$RESULTS_LOG"
        PASS=$((PASS + 1))
    else
        END_SEC=$(date +%s)
        ELAPSED=$((END_SEC - START_SEC))
        echo "  ✗ FAILED after ${ELAPSED}s"
        echo "FAIL|${study}|${scenario}|${ELAPSED}s" >> "$RESULTS_LOG"
        FAIL=$((FAIL + 1))
    fi
    
done < "$MANIFEST"

echo ""
echo "============================================"
echo " Batch Complete: $PASS passed, $FAIL failed out of $COUNT"
echo " Results log: $RESULTS_LOG"
echo " Finished: $(date)"
echo "============================================"
