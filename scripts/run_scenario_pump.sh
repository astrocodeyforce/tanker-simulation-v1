#!/bin/bash
###############################################################################
# run_scenario_pump.sh — Compile and run TankerDischargePump scenario
#
# Same as run_scenario_v2.sh but uses the pump model.
# Extra YAML keys: pump_max_flow_gpm (air-limited max GPM)
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

MODEL_FILE="/work/modelica/TankerDischargePump.mo"
if [ ! -f "$MODEL_FILE" ]; then
    echo "ERROR: Model not found: $MODEL_FILE"
    exit 1
fi

WORK_DIR="/tmp/sim_work_$$"
DATA_DIR="/work/data/runs"

echo "============================================"
echo " TankerDischargePump Scenario Runner"
echo " Config: $(basename "$CONFIG_FILE")"
echo " Time:   $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "============================================"

# ---- Parse YAML → override string for pump model ----
echo "Step 1: Parsing config..."

OVERRIDE_STRING=$(python3 - <<'PYEOF'
import sys, os, re, json

config_file = os.environ["CONFIG_FILE"]
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
            if not val.startswith('"') and not val.startswith("'"):
                val = re.split(r'\s+#', val, maxsplit=1)[0].strip()
            val = val.strip('"').strip("'")
            try:
                if "." in val:
                    config[key] = float(val)
                else:
                    config[key] = int(val)
            except ValueError:
                config[key] = val

GAL_TO_M3 = 0.00378541
PSI_TO_PA = 6894.76
FT_TO_M = 0.3048
IN_TO_M = 0.0254
CP_TO_PAS = 0.001
MM_TO_M = 0.001
GPM_TO_M3S = 6.30902e-5

def g(key, default=0):
    return config.get(key, default)

overrides = {
    "V_tank": g("tank_total_volume_gal", 7000) * GAL_TO_M3,
    "D_tank": g("tank_diameter_in", 75) * IN_TO_M,
    "L_tank": g("tank_length_ft", 0) * FT_TO_M,
    "V_liquid_0": g("initial_liquid_volume_gal", 6500) * GAL_TO_M3,
    "P_atm": g("ambient_pressure_psia", 14.696) * PSI_TO_PA,
    "T_gas_0": g("gas_temperature_C", 20.0) + 273.15,
    "rho_L": g("liquid_density_kg_m3", 1000.0),
    "mu_L": g("liquid_viscosity_cP", 100.0) * CP_TO_PAS,
    "D_valve": g("valve_diameter_in", 3.0) * IN_TO_M,
    "K_valve_open": g("valve_K_open", 0.2),
    "u_valve": g("valve_opening_fraction", 1.0),
    "D_pipe1": g("pipe1_diameter_in", 3.0) * IN_TO_M,
    "L_pipe1": g("pipe1_length_ft", 25.0) * FT_TO_M,
    "eps_pipe1": g("pipe1_roughness_mm", 0.01) * MM_TO_M,
    "K_pipe1": g("pipe1_K_minor", 1.0),
    "D_pipe2": g("pipe2_diameter_in", 3.0) * IN_TO_M,
    "L_pipe2": g("pipe2_length_ft", 25.0) * FT_TO_M,
    "eps_pipe2": g("pipe2_roughness_mm", 0.01) * MM_TO_M,
    "K_pipe2": g("pipe2_K_minor", 1.0),
    "dz_total": g("elevation_change_ft", 0.0) * FT_TO_M,
    "P_receiver": g("ambient_pressure_psia", 14.696) * PSI_TO_PA + g("receiver_pressure_psig", 0.0) * PSI_TO_PA,
    "V_liquid_min": g("min_liquid_volume_gal", 10.0) * GAL_TO_M3,
    "Q_pump_max": g("pump_max_flow_gpm", 47.5) * GPM_TO_M3S,
}

print(",".join(f"{k}={v}" for k, v in overrides.items()))
PYEOF
)

if [ -z "$OVERRIDE_STRING" ]; then
    echo "ERROR: Failed to parse config"
    exit 1
fi
echo "  Overrides: ${OVERRIDE_STRING:0:120}..."

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
")

STOP_TIME=$(python3 -c "
import re, os
with open(os.environ['CONFIG_FILE']) as f:
    for line in f:
        m = re.match(r'^stop_time_s\s*:\s*(\S+)', line.strip())
        if m: print(m.group(1)); break
    else: print('36000')
")

INTERVAL=$(python3 -c "
import re, os
with open(os.environ['CONFIG_FILE']) as f:
    for line in f:
        m = re.match(r'^output_interval_s\s*:\s*(\S+)', line.strip())
        if m: print(m.group(1)); break
    else: print('1.0')
")

TIMESTAMP=$(date -u '+%Y%m%d_%H%M%S')
RUN_DIR="$DATA_DIR/${TIMESTAMP}_${SCENARIO_NAME}"
mkdir -p "$RUN_DIR" "$WORK_DIR"
cp "$CONFIG_FILE" "$RUN_DIR/inputs.yaml"

echo "  Scenario: $SCENARIO_NAME"
echo "  Run dir:  $RUN_DIR"
echo "  Stop:     $STOP_TIME s, Interval: $INTERVAL s"

# ---- Compile ----
echo "Step 2: Compiling TankerDischargePump..."
cd "$WORK_DIR"

cat > build_pump.mos <<MOSEOF
loadFile("$MODEL_FILE");
getErrorString();
buildModel(TankerDischargePump, stopTime=$STOP_TIME, numberOfIntervals=$(python3 -c "print(int(float('$STOP_TIME')/float('$INTERVAL')))"), tolerance=1e-6, outputFormat="csv", simflags="-override $OVERRIDE_STRING");
getErrorString();
MOSEOF

omc build_pump.mos 2>&1 | tail -20
if [ ! -f TankerDischargePump ]; then
    echo "FATAL: Compilation failed!"
    cat build_pump.mos
    exit 1
fi
echo "  Compilation OK"

# ---- Run ----
echo "Step 3: Running simulation..."
./TankerDischargePump -override "$OVERRIDE_STRING" 2>&1 | tail -5
echo "  Simulation complete"

# ---- Export ----
echo "Step 4: Exporting results..."
if [ -f TankerDischargePump_res.csv ]; then
    cp TankerDischargePump_res.csv "$RUN_DIR/outputs.csv"
    WC=$(wc -l < "$RUN_DIR/outputs.csv")
    echo "  Exported $WC rows to $RUN_DIR/outputs.csv"
else
    echo "ERROR: No result CSV found!"
    ls -la "$WORK_DIR/"
    exit 1
fi

# ---- Summary line ----
echo "Step 5: Quick summary..."
python3 - "$RUN_DIR/outputs.csv" <<'SUMEOF'
import sys, csv
f = open(sys.argv[1])
reader = csv.DictReader(f)
rows = list(reader)
f.close()
if not rows:
    print("  WARNING: Empty results"); sys.exit(0)

# Find when flow stops
transfer_time = 0
peak_flow = 0
for r in rows:
    q = float(r.get("Q_L_gpm", 0))
    if q > 0.01:
        transfer_time = float(r["time"])
    if q > peak_flow:
        peak_flow = q

print(f"  Transfer time : {transfer_time/60:.1f} min")
print(f"  Peak flow     : {peak_flow:.1f} GPM")
print(f"  Final transfer: {float(rows[-1].get('V_transferred_gal', 0)):.0f} gal")
SUMEOF

echo "============================================"
echo " DONE: $RUN_DIR"
echo "============================================"

# Cleanup
rm -rf "$WORK_DIR"
