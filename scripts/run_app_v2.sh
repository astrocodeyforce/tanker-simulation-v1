#!/bin/bash
###############################################################################
# run_app_v2.sh — Run all V2 TankerTransfer scenarios
#
# Usage:
#   cd /opt/sim-lab/truck-tanker-sim-env
#   ./scripts/run_app_v2.sh                    # all scenarios
#   ./scripts/run_app_v2.sh v2_baseline        # single scenario
###############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# All V2 scenario configs
ALL_SCENARIOS=(
    "config/v2_baseline.yaml"
    "config/v2_solvent.yaml"
    "config/v2_coating.yaml"
)

# Filter if specific scenario requested
if [ $# -ge 1 ]; then
    SPECIFIC="$1"
    MATCHED=()
    for s in "${ALL_SCENARIOS[@]}"; do
        if [[ "$s" == *"$SPECIFIC"* ]]; then
            MATCHED+=("$s")
        fi
    done
    if [ ${#MATCHED[@]} -eq 0 ]; then
        echo "ERROR: No scenario matching '$SPECIFIC'"
        echo "  Available:"
        for s in "${ALL_SCENARIOS[@]}"; do
            echo "    $(basename "$s" .yaml)"
        done
        exit 2
    fi
    ALL_SCENARIOS=("${MATCHED[@]}")
fi

N=${#ALL_SCENARIOS[@]}
echo "╔══════════════════════════════════════════════════╗"
echo "║   TankerTransfer V2 — Pipeline Runner            ║"
echo "║   Scenarios: ${N}                                      ║"
echo "║   $(date -u '+%Y-%m-%d %H:%M:%S UTC')                       ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Guard check — snapshot before
echo "--- Guard Check: Snapshot ---"
if [ -f "$SCRIPT_DIR/guard_check.sh" ]; then
    bash "$SCRIPT_DIR/guard_check.sh" --snapshot || { echo "GUARD SNAPSHOT FAILED"; exit 1; }
fi
echo ""

PASS=0
FAIL=0

for CONFIG in "${ALL_SCENARIOS[@]}"; do
    BASENAME=$(basename "$CONFIG" .yaml)
    echo "═══ Running: $BASENAME ═══"

    if docker compose run --rm --entrypoint "" openmodelica-runner \
        bash /work/scripts/run_scenario_v2.sh "/work/$CONFIG"; then
        echo "  PASS: $BASENAME"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $BASENAME"
        FAIL=$((FAIL + 1))
    fi
    echo ""
done

echo "╔══════════════════════════════════════════════════╗"
echo "║   Results: ${PASS} passed, ${FAIL} failed                    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Guard check — verify after
echo "--- Guard Check: Verify ---"
if [ -f "$SCRIPT_DIR/guard_check.sh" ]; then
    bash "$SCRIPT_DIR/guard_check.sh" --verify || { echo "GUARD VERIFY FAILED"; FAIL=$((FAIL + 1)); }
fi
echo ""

if [ $FAIL -gt 0 ]; then
    exit 1
fi
