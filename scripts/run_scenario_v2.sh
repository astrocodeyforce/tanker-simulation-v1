#!/bin/bash
###############################################################################
# run_scenario_v2.sh — Compile and run TankerTransferV2 scenario
#
# Runs INSIDE the OpenModelica container.
# Reads a v2 YAML config, converts to SI, compiles+runs, exports results.
#
# Usage:
#   bash /work/scripts/run_scenario_v2.sh /work/config/v2_baseline.yaml
###############################################################################

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <config_yaml_path>"
    exit 2
fi

CONFIG_FILE="$1"
export CONFIG_FILE
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config not found: $CONFIG_FILE"
    exit 1
fi

MODEL_FILE="/work/modelica/TankerTransferV2.mo"
if [ ! -f "$MODEL_FILE" ]; then
    echo "ERROR: Model not found: $MODEL_FILE"
    exit 1
fi

WORK_DIR="/tmp/sim_work_$$"
DATA_DIR="/work/data/runs"

echo "============================================"
echo " TankerTransferV2 Scenario Runner"
echo " Config: $(basename "$CONFIG_FILE")"
echo " Time:   $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "============================================"

# ---- Step 1: Parse YAML → Modelica override string ----
echo "Step 1: Parsing config..."

OVERRIDE_STRING=$(python3 /work/scripts/yaml_to_override_v2.py)
if [ -z "$OVERRIDE_STRING" ]; then
    echo "ERROR: Failed to parse config"
    exit 1
fi
echo "  Overrides: ${OVERRIDE_STRING:0:120}..."

# ---- Step 2: Get scenario name and sim settings ----
SCENARIO_NAME=$(python3 -c "
import re, os
with open(os.environ['CONFIG_FILE']) as f:
    for line in f:
        m = re.match(r'^scenario_name\s*:\s*(.+)$', line.strip())
        if m:
            val = m.group(1).strip()
            val = re.split(r'\s+#', val, maxsplit=1)[0].strip()
            print(val.strip('\"').strip(\"'\"))
            break
    else:
        print(os.path.splitext(os.path.basename(os.environ['CONFIG_FILE']))[0])
")

STOP_TIME=$(python3 -c "
import re, os
with open(os.environ['CONFIG_FILE']) as f:
    for line in f:
        m = re.match(r'^stop_time_s\s*:\s*(\S+)', line.strip())
        if m:
            val = re.split(r'\s+#', m.group(1), maxsplit=1)[0].strip()
            print(val); break
    else:
        print('7200')
")

OUTPUT_INTERVAL=$(python3 -c "
import re, os
with open(os.environ['CONFIG_FILE']) as f:
    for line in f:
        m = re.match(r'^output_interval_s\s*:\s*(\S+)', line.strip())
        if m:
            val = re.split(r'\s+#', m.group(1), maxsplit=1)[0].strip()
            print(val); break
    else:
        print('1.0')
")

N_INTERVALS=$(python3 -c "print(int(float('${STOP_TIME}') / float('${OUTPUT_INTERVAL}')))")

TIMESTAMP=$(date -u '+%Y%m%d_%H%M%S')
RUN_DIR="${DATA_DIR}/${TIMESTAMP}_${SCENARIO_NAME}"
mkdir -p "$RUN_DIR"

echo "Step 2: Run dir = $RUN_DIR"
echo "  stopTime=$STOP_TIME, intervals=$N_INTERVALS"
cp "$CONFIG_FILE" "${RUN_DIR}/inputs.yaml"

# ---- Step 3: Compile and simulate ----
echo "Step 3: Compiling and simulating..."

mkdir -p "$WORK_DIR"
cp "$MODEL_FILE" "$WORK_DIR/"
cd "$WORK_DIR"

cat > run.mos << OMSCRIPT
loadFile("TankerTransferV2.mo");
getErrorString();
simulate(TankerTransferV2,
  startTime=0,
  stopTime=${STOP_TIME},
  numberOfIntervals=${N_INTERVALS},
  tolerance=1e-6,
  outputFormat="csv",
  simflags="-override ${OVERRIDE_STRING}");
getErrorString();
if regularFileExists("TankerTransferV2_res.csv") then
  print("SIMULATION_SUCCESS\n");
else
  print("SIMULATION_FAILED\n");
end if;
OMSCRIPT

omc run.mos 2>&1 | tee omc_output.log

if grep -q "SIMULATION_SUCCESS" omc_output.log; then
    echo "  Simulation OK"
else
    echo "  SIMULATION FAILED"
    python3 -c "
import json, os
from datetime import datetime, timezone
log = {
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'scenario': '${SCENARIO_NAME}',
    'config_file': '${CONFIG_FILE}',
    'status': 'FAILED',
}
with open('${RUN_DIR}/run_log.json', 'w') as f:
    json.dump(log, f, indent=2)
"
    exit 1
fi

# ---- Step 4: Export results ----
echo "Step 4: Exporting results..."
RESULT_FILE="${WORK_DIR}/TankerTransferV2_res.csv"
OUTPUT_CSV="${RUN_DIR}/outputs.csv"

python3 /work/scripts/export_results_v2.py "$RESULT_FILE" "$OUTPUT_CSV"

# ---- Step 5: Write run log ----
echo "Step 5: Writing run log..."
python3 -c "
import json, os
from datetime import datetime, timezone
run_dir = '${RUN_DIR}'
output_csv = '${OUTPUT_CSV}'
rows = 0
if os.path.isfile(output_csv):
    with open(output_csv) as f:
        rows = sum(1 for _ in f) - 1
log = {
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'scenario': '${SCENARIO_NAME}',
    'config_file': '${CONFIG_FILE}',
    'model_version': 'TankerTransferV2',
    'outputs': {'csv': output_csv, 'output_rows': rows},
    'status': 'success',
}
with open(os.path.join(run_dir, 'run_log.json'), 'w') as f:
    json.dump(log, f, indent=2)
print(f'  Log written: {run_dir}/run_log.json')
"

# Cleanup
cd /
rm -rf "$WORK_DIR"

echo "============================================"
echo " Scenario complete: ${SCENARIO_NAME}"
echo " Output: ${OUTPUT_CSV}"
echo "============================================"
