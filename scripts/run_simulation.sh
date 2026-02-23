#!/bin/bash
###############################################################################
# run_simulation.sh — Compile and run HelloWorld Modelica model
#
# This script runs INSIDE the OpenModelica container.
# It compiles HelloWorld.mo, runs the simulation, and exports CSV output.
#
# Exit behavior: Fails loudly on any error (set -euo pipefail)
###############################################################################

set -euo pipefail

MODEL_NAME="HelloWorld"
MODEL_FILE="/work/models/${MODEL_NAME}.mo"
OUTPUT_DIR="/work/outputs"
WORK_DIR="/tmp/sim_work"

echo "============================================"
echo " Sim-Lab: OpenModelica Simulation Runner"
echo " Model: ${MODEL_NAME}"
echo " Time:  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "============================================"

# ---- Validate input ----
if [ ! -f "$MODEL_FILE" ]; then
    echo "❌ ERROR: Model file not found: $MODEL_FILE"
    exit 1
fi

# ---- Prepare work directory ----
mkdir -p "$WORK_DIR" "$OUTPUT_DIR"
cp "$MODEL_FILE" "$WORK_DIR/"
cd "$WORK_DIR"

echo ""
echo "📦 Step 1: Compiling model..."

# Create an OpenModelica script to compile and simulate
cat > run.mos << 'OMSCRIPT'
// Load and simulate HelloWorld
loadFile("HelloWorld.mo");
getErrorString();

// Simulate with parameters from the annotation
simulate(HelloWorld, startTime=0, stopTime=5, numberOfIntervals=500, tolerance=1e-6, outputFormat="csv");
getErrorString();

// Check if result file exists
if regularFileExists("HelloWorld_res.csv") then
  print("SIMULATION_SUCCESS\n");
else
  print("SIMULATION_FAILED\n");
end if;
OMSCRIPT

# ---- Run OpenModelica compiler ----
echo "Running: omc run.mos"
omc run.mos 2>&1 | tee omc_output.log

# ---- Check for success ----
if grep -q "SIMULATION_SUCCESS" omc_output.log; then
    echo ""
    echo "✅ Step 1 Complete: Model compiled and simulated successfully"
else
    echo ""
    echo "❌ ERROR: Simulation failed. Check omc_output.log"
    cat omc_output.log
    exit 1
fi

# ---- Copy results to output directory ----
echo ""
echo "📦 Step 2: Exporting results..."

if [ -f "${MODEL_NAME}_res.csv" ]; then
    cp "${MODEL_NAME}_res.csv" "${OUTPUT_DIR}/${MODEL_NAME}_res.csv"
    LINES=$(wc -l < "${OUTPUT_DIR}/${MODEL_NAME}_res.csv")
    echo "✅ Step 2 Complete: ${OUTPUT_DIR}/${MODEL_NAME}_res.csv (${LINES} lines)"
else
    echo "❌ ERROR: Result CSV not found: ${MODEL_NAME}_res.csv"
    ls -la "$WORK_DIR"
    exit 1
fi

echo ""
echo "============================================"
echo " ✅ Simulation completed successfully"
echo " Output: ${OUTPUT_DIR}/${MODEL_NAME}_res.csv"
echo "============================================"
