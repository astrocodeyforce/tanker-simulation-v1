#!/bin/bash
###############################################################################
# run_scenario.sh — Compile and run a TankerTransfer scenario
#
# This script runs INSIDE the OpenModelica container.
# It reads a YAML config, converts parameters, compiles the Modelica model,
# runs the simulation, and exports results.
#
# Usage:
#   bash /work/scripts/run_scenario.sh /work/config/scenario_A_pressurize_only.yaml
#
# Requires: omc, python3 (both available in openmodelica container)
###############################################################################

set -euo pipefail

# ---- Argument check ----
if [ $# -lt 1 ]; then
    echo "Usage: $0 <config_yaml_path>"
    echo "Example: $0 /work/config/scenario_A_pressurize_only.yaml"
    exit 2
fi

CONFIG_FILE="$1"
export CONFIG_FILE
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

MODEL_FILE="/work/modelica/TankerTransfer.mo"
if [ ! -f "$MODEL_FILE" ]; then
    echo "❌ ERROR: Model file not found: $MODEL_FILE"
    exit 1
fi

WORK_DIR="/tmp/sim_work_$$"
DATA_DIR="/work/data/runs"

echo "============================================"
echo " TankerTransfer Scenario Runner"
echo " Config: $(basename "$CONFIG_FILE")"
echo " Time:   $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "============================================"
echo ""

# ---- Step 1: Parse YAML config and convert to Modelica overrides ----
echo "📦 Step 1: Parsing config and converting units..."

# Use inline Python to parse YAML and produce Modelica override string
# (pyyaml may not be available, so we parse manually)
OVERRIDE_STRING=$(python3 << 'PYEOF'
import sys, os, re, json

config_file = os.environ.get("CONFIG_FILE", "")
if not config_file:
    print("ERROR: CONFIG_FILE not set", file=sys.stderr)
    sys.exit(1)

# Simple YAML parser (no pyyaml dependency)
config = {}
with open(config_file) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^(\w+)\s*:\s*(.+)$', line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            # Strip inline comments (# after value)
            # Be careful not to strip # inside quoted strings
            if not val.startswith('"') and not val.startswith("'"):
                val = re.split(r'\s+#', val, maxsplit=1)[0].strip()
            val = val.strip('"').strip("'")
            # Try to parse as number
            try:
                if "." in val:
                    config[key] = float(val)
                else:
                    config[key] = int(val)
            except ValueError:
                config[key] = val

# ---- Unit conversions: config units → SI (Modelica model units) ----
gal_to_m3 = 0.00378541
psi_to_pa = 6894.76
ft_to_m = 0.3048
inch_to_m = 0.0254
cP_to_Pas = 0.001
scfm_to_m3s = 0.000471947
gpm_to_m3s = 6.30902e-5

# Gas constant and standard conditions
R_air = 287.05
T_std = 288.15  # 15°C
P_std = 101325.0

# Tank
V_tank_total = config.get("tanker_total_volume_gal", 4500) * gal_to_m3
fill = config.get("initial_fill_fraction", 0.90)
V_liquid_0 = V_tank_total * fill

# Pressures
P_max_psig = config.get("max_tank_pressure_psig", 30.0)
P_ambient_psia = config.get("ambient_pressure_psia", 14.7)
P_receiver_psig = config.get("receiver_backpressure_psig", 0.0)

P_max = (P_max_psig + P_ambient_psia) * psi_to_pa
P_ambient = P_ambient_psia * psi_to_pa
P_receiver = (P_receiver_psig + P_ambient_psia) * psi_to_pa

# Temperature
T_C = config.get("temperature_C", 25.0)
T_K = T_C + 273.15

# Air supply
air_scfm = config.get("air_supply_scfm", 19.0)
mdot_air_total = air_scfm * scfm_to_m3s * P_std / (R_air * T_std)

f_tank = config.get("air_split_fraction_to_tank", 1.0)
f_pump = config.get("air_split_fraction_to_pump", 0.0)

# Liquid
rho_liq = config.get("density_kg_m3", 880.0)
mu_liq = config.get("viscosity_cP", 220.0) * cP_to_Pas

# Hose
D_hose = config.get("hose_ID_in", 2.0) * inch_to_m
L_hose = config.get("hose_length_ft", 50.0) * ft_to_m
eps_rough = config.get("roughness_mm", 0.0) * 0.001
K_minor = config.get("minor_loss_K_total", 5.0)
dz = config.get("elevation_change_ft", 0.0) * ft_to_m

# Pump
pump_eff = config.get("pump_efficiency_gpm_per_scfm", 0.5)
Q_pump_per_scfm = pump_eff * gpm_to_m3s  # m³/s per SCFM of air

# Simulation
stop_time = config.get("stop_time_s", 7200)
n_intervals = int(stop_time / config.get("output_interval_s", 1.0))

# Build override string
overrides = {
    "V_tank_total": V_tank_total,
    "V_liquid_0": V_liquid_0,
    "P_max": P_max,
    "P_ambient": P_ambient,
    "P_receiver": P_receiver,
    "T": T_K,
    "mdot_air_total": mdot_air_total,
    "f_tank": f_tank,
    "f_pump": f_pump,
    "rho_liq": rho_liq,
    "mu_liq": mu_liq,
    "D_hose": D_hose,
    "L_hose": L_hose,
    "eps_rough": eps_rough,
    "K_minor": K_minor,
    "dz": dz,
    "Q_pump_per_scfm_air": Q_pump_per_scfm,
}

override_str = ",".join(f"{k}={v}" for k, v in overrides.items())
print(override_str)

# Also write the config as JSON for run_log
config_json = json.dumps(config, indent=2)
json_path = os.environ.get("CONFIG_JSON_PATH", "/tmp/config_parsed.json")
with open(json_path, "w") as jf:
    jf.write(config_json)

# Write computed SI values as JSON too
si_values = {k: v for k, v in overrides.items()}
si_values["stop_time"] = stop_time
si_values["n_intervals"] = n_intervals
si_json_path = os.environ.get("SI_JSON_PATH", "/tmp/si_values.json")
with open(si_json_path, "w") as sf:
    json.dump(si_values, sf, indent=2)

PYEOF
)

if [ -z "$OVERRIDE_STRING" ]; then
    echo "❌ ERROR: Failed to parse config file"
    exit 1
fi

echo "  Override string: ${OVERRIDE_STRING:0:120}..."
echo ""

# ---- Step 2: Get scenario name and create run directory ----
SCENARIO_NAME=$(python3 -c "
import re, os
config_file = os.environ['CONFIG_FILE']
with open(config_file) as f:
    for line in f:
        m = re.match(r'^scenario_name\s*:\s*(.+)$', line.strip())
        if m:
            print(m.group(1).strip().strip('\"').strip(\"'\"))
            break
    else:
        # Fallback: use filename without extension
        print(os.path.splitext(os.path.basename(config_file))[0])
")

TIMESTAMP=$(date -u '+%Y%m%d_%H%M%S')
RUN_DIR="${DATA_DIR}/${TIMESTAMP}_${SCENARIO_NAME}"
mkdir -p "$RUN_DIR"

echo "📦 Step 2: Run directory: $RUN_DIR"
cp "$CONFIG_FILE" "${RUN_DIR}/inputs.yaml"
echo ""

# ---- Step 3: Get simulation settings ----
STOP_TIME=$(python3 -c "
import re, os
with open(os.environ['CONFIG_FILE']) as f:
    for line in f:
        m = re.match(r'^stop_time_s\s*:\s*(\S+)', line.strip())
        if m:
            print(m.group(1))
            break
    else:
        print('7200')
")

OUTPUT_INTERVAL=$(python3 -c "
import re, os
with open(os.environ['CONFIG_FILE']) as f:
    for line in f:
        m = re.match(r'^output_interval_s\s*:\s*(\S+)', line.strip())
        if m:
            print(m.group(1))
            break
    else:
        print('1.0')
")

N_INTERVALS=$(python3 -c "print(int(float('${STOP_TIME}') / float('${OUTPUT_INTERVAL}')))")

echo "  Simulation: stopTime=$STOP_TIME, intervals=$N_INTERVALS"

# ---- Step 4: Compile and simulate ----
echo ""
echo "📦 Step 3: Compiling and simulating TankerTransfer..."

mkdir -p "$WORK_DIR"
cp "$MODEL_FILE" "$WORK_DIR/"
cd "$WORK_DIR"

# Create OpenModelica script
cat > run.mos << OMSCRIPT
// Load TankerTransfer model
loadFile("TankerTransfer.mo");
getErrorString();

// Simulate with overrides from config
simulate(TankerTransfer,
  startTime=0,
  stopTime=${STOP_TIME},
  numberOfIntervals=${N_INTERVALS},
  tolerance=1e-6,
  outputFormat="csv",
  simflags="-override ${OVERRIDE_STRING}");
getErrorString();

// Check result
if regularFileExists("TankerTransfer_res.csv") then
  print("SIMULATION_SUCCESS\n");
else
  print("SIMULATION_FAILED\n");
end if;
OMSCRIPT

echo "  Running: omc run.mos"
omc run.mos 2>&1 | tee omc_output.log

if grep -q "SIMULATION_SUCCESS" omc_output.log; then
    echo ""
    echo "  ✅ Simulation completed successfully"
else
    echo ""
    echo "  ❌ Simulation FAILED. omc output:"
    cat omc_output.log
    # Write failure log
    python3 -c "
import json, os
from datetime import datetime, timezone
log = {
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'scenario': '${SCENARIO_NAME}',
    'config_file': '${CONFIG_FILE}',
    'status': 'FAILED',
    'error': 'OpenModelica simulation did not produce result file'
}
with open('${RUN_DIR}/run_log.json', 'w') as f:
    json.dump(log, f, indent=2)
"
    exit 1
fi

# ---- Step 5: Export results ----
echo ""
echo "📦 Step 4: Exporting results..."

RESULT_FILE="${WORK_DIR}/TankerTransfer_res.csv"
OUTPUT_CSV="${RUN_DIR}/outputs.csv"

if [ -f "$RESULT_FILE" ]; then
    python3 /work/scripts/export_results.py "$RESULT_FILE" "$OUTPUT_CSV"
else
    echo "  ❌ ERROR: Result file not found: $RESULT_FILE"
    exit 1
fi

# ---- Step 6: Write run log ----
echo ""
echo "📦 Step 5: Writing run log..."

export CONFIG_JSON_PATH="/tmp/config_parsed.json"
python3 << PYLOG
import json, os
from datetime import datetime, timezone

run_dir = "${RUN_DIR}"
scenario = "${SCENARIO_NAME}"
config_file = "${CONFIG_FILE}"
output_csv = "${OUTPUT_CSV}"

# Load parsed config
config = {}
config_json = os.environ.get("CONFIG_JSON_PATH", "/tmp/config_parsed.json")
if os.path.isfile(config_json):
    with open(config_json) as f:
        config = json.load(f)

# Count output rows
output_rows = 0
if os.path.isfile(output_csv):
    with open(output_csv) as f:
        output_rows = sum(1 for _ in f) - 1  # minus header

log = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "scenario": scenario,
    "config_file": config_file,
    "parameters": config,
    "outputs": {
        "csv": output_csv,
        "plots": os.path.join(run_dir, "plots.png"),
        "output_rows": output_rows,
    },
    "status": "success",
}

log_path = os.path.join(run_dir, "run_log.json")
with open(log_path, "w") as f:
    json.dump(log, f, indent=2)

print(f"  ✅ Run log written: {log_path}")
PYLOG

# ---- Cleanup ----
cd /
rm -rf "$WORK_DIR"

echo ""
echo "============================================"
echo " ✅ Scenario complete: ${SCENARIO_NAME}"
echo " Run dir: ${RUN_DIR}"
echo " Output:  ${OUTPUT_CSV}"
echo "============================================"
