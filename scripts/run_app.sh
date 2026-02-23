#!/bin/bash
###############################################################################
# run_app.sh — Master Application Execution Wrapper
#
# Runs all 3 TankerTransfer scenarios, generates plots, runs guard check,
# and writes logs. One command to execute the full application pipeline.
#
# Usage:
#   cd /opt/sim-lab/truck-tanker-sim-env
#   ./scripts/run_app.sh
#
# Or run a single scenario:
#   ./scripts/run_app.sh scenario_A_pressurize_only
#
# Exit codes:
#   0 = All steps passed
#   1 = A step failed
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

LOG_FILE="logs/EXECUTION_LOG.md"
RUN_START=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

# All scenario configs
ALL_SCENARIOS=(
    "config/scenario_A_pressurize_only.yaml"
    "config/scenario_B_split_air.yaml"
    "config/scenario_C_pump_only.yaml"
)

# If a specific scenario was requested, filter
if [ $# -ge 1 ]; then
    SPECIFIC="$1"
    MATCHED=()
    for s in "${ALL_SCENARIOS[@]}"; do
        if [[ "$s" == *"$SPECIFIC"* ]]; then
            MATCHED+=("$s")
        fi
    done
    if [ ${#MATCHED[@]} -eq 0 ]; then
        echo "❌ ERROR: No scenario matching '$SPECIFIC'"
        echo "  Available:"
        for s in "${ALL_SCENARIOS[@]}"; do
            echo "    $(basename "$s" .yaml)"
        done
        exit 2
    fi
    ALL_SCENARIOS=("${MATCHED[@]}")
fi

N_SCENARIOS=${#ALL_SCENARIOS[@]}

echo "╔══════════════════════════════════════════════════╗"
echo "║   TankerTransfer — Application Pipeline          ║"
echo "║   Scenarios: ${N_SCENARIOS}                                    ║"
echo "║   Started:   ${RUN_START}              ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ---- Step 1: Guard Snapshot ----
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1: Capturing baseline snapshot..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
GUARD_RESULT="PASS"
if ! ./scripts/guard_check.sh --snapshot; then
    echo "⚠️  Warning: Guard snapshot had issues"
    GUARD_RESULT="WARN"
fi
echo ""

# ---- Step 2: Run Each Scenario ----
SCENARIO_RESULTS=()
RUN_DIRS=()
TOTAL_FAILURES=0

for i in "${!ALL_SCENARIOS[@]}"; do
    CONFIG="${ALL_SCENARIOS[$i]}"
    SCENARIO_NAME=$(basename "$CONFIG" .yaml)
    STEP_NUM=$((i + 2))

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Step ${STEP_NUM}: Scenario — ${SCENARIO_NAME}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # --- Run simulation ---
    SIM_OK=true
    if ! docker compose run --rm openmodelica-runner \
        /work/scripts/run_scenario.sh "/work/${CONFIG}"; then
        echo "  ❌ Simulation failed for ${SCENARIO_NAME}"
        SIM_OK=false
        TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
    fi

    # --- Find the latest run directory for this scenario ---
    LATEST_RUN=""
    if [ "$SIM_OK" = true ]; then
        LATEST_RUN=$(ls -td data/runs/*_${SCENARIO_NAME}/ 2>/dev/null | head -1)
    fi

    # --- Run visualization ---
    VIZ_OK=true
    if [ -n "$LATEST_RUN" ] && [ -f "${LATEST_RUN}outputs.csv" ]; then
        echo ""
        echo "  Running visualization for ${SCENARIO_NAME}..."
        if ! docker compose run --rm python-plotter \
            "pip install --quiet matplotlib && python /work/python/plot_results.py /work/${LATEST_RUN}outputs.csv"; then
            echo "  ❌ Visualization failed for ${SCENARIO_NAME}"
            VIZ_OK=false
            TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
        fi
    else
        echo "  ⏭️  Skipping visualization — no CSV output"
        VIZ_OK=false
    fi

    # Record results
    if [ "$SIM_OK" = true ] && [ "$VIZ_OK" = true ]; then
        SCENARIO_RESULTS+=("✅ ${SCENARIO_NAME}")
    elif [ "$SIM_OK" = true ]; then
        SCENARIO_RESULTS+=("⚠️  ${SCENARIO_NAME} (sim OK, viz failed)")
    else
        SCENARIO_RESULTS+=("❌ ${SCENARIO_NAME}")
    fi
    RUN_DIRS+=("${LATEST_RUN:-none}")

    echo ""
done

# ---- Step N+2: Generate comparison report ----
REPORT_STEP=$((N_SCENARIOS + 2))
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step ${REPORT_STEP}: Generating comparison report..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose run --rm python-plotter \
    "pip install --quiet matplotlib && python /work/python/make_report.py /work/data/runs" \
    || echo "  ⚠️  Report generation failed (non-critical)"
echo ""

# ---- Step N+3: Guard Verify ----
VERIFY_STEP=$((N_SCENARIOS + 3))
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step ${VERIFY_STEP}: Guard integrity verification..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ! ./scripts/guard_check.sh --verify; then
    echo "  ❌ GUARD CHECK FAILED — investigate immediately!"
    GUARD_RESULT="FAIL"
    TOTAL_FAILURES=$((TOTAL_FAILURES + 1))
else
    GUARD_RESULT="PASS"
fi
echo ""

# ---- Log to EXECUTION_LOG.md ----
RUN_END=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
OVERALL="SUCCESS"
[ "$TOTAL_FAILURES" -gt 0 ] && OVERALL="FAILED (${TOTAL_FAILURES} failures)"

cat >> "$LOG_FILE" << EOF

---

## App Run — ${RUN_START}

**Overall: ${OVERALL}**

### Scenarios
$(for r in "${SCENARIO_RESULTS[@]}"; do echo "- ${r}"; done)

### Guard Check: ${GUARD_RESULT}

### Run Directories
$(for d in "${RUN_DIRS[@]}"; do echo "- ${d}"; done)

### Completed: ${RUN_END}
EOF

# ---- Final Summary ----
echo "╔══════════════════════════════════════════════════╗"
echo "║   Application Pipeline Complete                  ║"
echo "║   Result: ${OVERALL}"
echo "╠══════════════════════════════════════════════════╣"
for r in "${SCENARIO_RESULTS[@]}"; do
    echo "║   ${r}"
done
echo "║   Guard: ${GUARD_RESULT}"
echo "║   Log: ${LOG_FILE}"
echo "╚══════════════════════════════════════════════════╝"

[ "$TOTAL_FAILURES" -eq 0 ] && exit 0 || exit 1
