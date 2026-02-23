#!/bin/bash
###############################################################################
# run_all.sh — Master Execution Workflow
#
# Runs the complete sim-lab pipeline in the correct sequence:
#   1. Capture baseline Docker state snapshot
#   2. Run Modelica simulation (compile + execute HelloWorld)
#   3. Run Python visualization (CSV → PNG)
#   4. Run guard integrity check
#   5. Log results to EXECUTION_LOG.md
#
# Usage:
#   cd /opt/sim-lab/truck-tanker-sim-env
#   ./scripts/run_all.sh
#
# Exit codes:
#   0 = All steps passed
#   1 = A step failed (details in output and logs)
###############################################################################

set -euo pipefail

# ---- Configuration ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_DIR}/logs/EXECUTION_LOG.md"
RUN_START=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

cd "$PROJECT_DIR"

# ---- Track run number ----
if [ -f "$LOG_FILE" ]; then
    LAST_RUN=$(grep -c "^## Run #" "$LOG_FILE" 2>/dev/null || echo "0")
else
    LAST_RUN=0
fi
RUN_NUM=$((LAST_RUN + 1))

echo "╔══════════════════════════════════════════════╗"
echo "║   Sim-Lab: Master Execution Pipeline         ║"
echo "║   Run #${RUN_NUM}                                      ║"
echo "║   Started: ${RUN_START}             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Results tracking
STEP1_RESULT="❌ FAIL"
STEP2_RESULT="❌ FAIL"
STEP3_RESULT="❌ FAIL"
STEP4_RESULT="❌ FAIL"
STEP1_DURATION="—"
STEP2_DURATION="—"
STEP3_DURATION="—"
STEP4_DURATION="—"
ANOMALIES="None"
OVERALL="FAILED"

# ---- STEP 1: Baseline Snapshot ----
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1/4: Capturing baseline snapshot..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
STEP_START=$(date +%s)

if ./scripts/guard_check.sh --snapshot; then
    STEP1_RESULT="✅ PASS"
else
    STEP1_RESULT="❌ FAIL"
    ANOMALIES="Baseline snapshot failed"
fi

STEP_END=$(date +%s)
STEP1_DURATION="$((STEP_END - STEP_START))s"
echo ""

# ---- STEP 2: Modelica Simulation ----
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 2/4: Running Modelica simulation..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
STEP_START=$(date +%s)

if docker compose run --rm openmodelica; then
    STEP2_RESULT="✅ PASS"
else
    STEP2_RESULT="❌ FAIL"
    ANOMALIES="Modelica simulation failed (exit code: $?)"
    echo ""
    echo "⚠️  Simulation failed — continuing to guard check"
fi

STEP_END=$(date +%s)
STEP2_DURATION="$((STEP_END - STEP_START))s"
echo ""

# ---- STEP 3: Python Visualization ----
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 3/4: Running Python visualization..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
STEP_START=$(date +%s)

if [ -f "outputs/HelloWorld_res.csv" ]; then
    if docker compose run --rm python-viz; then
        STEP3_RESULT="✅ PASS"
    else
        STEP3_RESULT="❌ FAIL"
        ANOMALIES="Python visualization failed (exit code: $?)"
    fi
else
    STEP3_RESULT="⏭️ SKIP"
    echo "  Skipped: No CSV output from simulation"
    ANOMALIES="Visualization skipped — no simulation output"
fi

STEP_END=$(date +%s)
STEP3_DURATION="$((STEP_END - STEP_START))s"
echo ""

# ---- STEP 4: Guard Integrity Check ----
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 4/4: Running integrity verification..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
STEP_START=$(date +%s)

if ./scripts/guard_check.sh --verify; then
    STEP4_RESULT="✅ PASS"
else
    STEP4_RESULT="❌ FAIL"
    ANOMALIES="Guard integrity check FAILED — INVESTIGATE IMMEDIATELY"
fi

STEP_END=$(date +%s)
STEP4_DURATION="$((STEP_END - STEP_START))s"
echo ""

# ---- Determine Overall Result ----
if [[ "$STEP1_RESULT" == *"PASS"* ]] && \
   [[ "$STEP2_RESULT" == *"PASS"* ]] && \
   [[ "$STEP3_RESULT" == *"PASS"* ]] && \
   [[ "$STEP4_RESULT" == *"PASS"* ]]; then
    OVERALL="SUCCESS"
fi

# Check for output files
CSV_EXISTS="❌"
PNG_EXISTS="❌"
[ -f "outputs/HelloWorld_res.csv" ] && CSV_EXISTS="✅"
[ -f "outputs/HelloWorld_plot.png" ] && PNG_EXISTS="✅"

# ---- Log to EXECUTION_LOG.md ----
RUN_END=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

cat >> "$LOG_FILE" << EOF

---

## Run #${RUN_NUM} — ${RUN_START}

**Overall Result: ${OVERALL}**

### Pipeline Steps
| Step | Command | Result | Duration |
|------|---------|--------|----------|
| 1 | guard_check.sh --snapshot | ${STEP1_RESULT} | ${STEP1_DURATION} |
| 2 | docker compose run openmodelica | ${STEP2_RESULT} | ${STEP2_DURATION} |
| 3 | docker compose run python-viz | ${STEP3_RESULT} | ${STEP3_DURATION} |
| 4 | guard_check.sh --verify | ${STEP4_RESULT} | ${STEP4_DURATION} |

### Outputs Generated
- ${CSV_EXISTS} outputs/HelloWorld_res.csv
- ${PNG_EXISTS} outputs/HelloWorld_plot.png

### Integrity Check
- Containers: ${STEP4_RESULT}
- Networks: ${STEP4_RESULT}
- Volumes: ${STEP4_RESULT}

### Anomalies
${ANOMALIES}

### Completed
${RUN_END}
EOF

# ---- Final Summary ----
echo "╔══════════════════════════════════════════════╗"
echo "║   Run #${RUN_NUM} Complete — ${OVERALL}"
echo "║                                              ║"
echo "║   Step 1 (Snapshot):      ${STEP1_RESULT}  (${STEP1_DURATION})"
echo "║   Step 2 (Simulation):    ${STEP2_RESULT}  (${STEP2_DURATION})"
echo "║   Step 3 (Visualization): ${STEP3_RESULT}  (${STEP3_DURATION})"
echo "║   Step 4 (Guard Check):   ${STEP4_RESULT}  (${STEP4_DURATION})"
echo "║                                              ║"
echo "║   CSV: ${CSV_EXISTS}  PNG: ${PNG_EXISTS}"
echo "║   Log: logs/EXECUTION_LOG.md                 ║"
echo "╚══════════════════════════════════════════════╝"

if [ "$OVERALL" = "FAILED" ]; then
    exit 1
fi
