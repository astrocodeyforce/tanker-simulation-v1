#!/usr/bin/env python3
"""
yaml_to_override_v2.py — Convert v2 YAML config to Modelica override string.

Reads CONFIG_FILE env var, parses YAML, converts engineering units to SI,
prints the override string to stdout for use by run_scenario_v2.sh.
"""

import sys
import os
import re
import json

config_file = os.environ.get("CONFIG_FILE", "")
if not config_file:
    print("ERROR: CONFIG_FILE not set", file=sys.stderr)
    sys.exit(1)

# ── Simple YAML parser (no pyyaml dependency) ──
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

# ── Unit conversion constants ──
GAL_TO_M3 = 0.00378541
PSI_TO_PA = 6894.76
FT_TO_M = 0.3048
IN_TO_M = 0.0254
CP_TO_PAS = 0.001
MM_TO_M = 0.001
SCFM_TO_M3S = 0.000471947
R_AIR = 287.05
T_STD = 288.15  # 15°C
P_STD = 101325.0

# ── Read config values with defaults ──
def g(key, default=0):
    return config.get(key, default)

# Tank geometry
V_tank = g("tank_total_volume_gal", 7000) * GAL_TO_M3
D_tank = g("tank_diameter_in", 75) * IN_TO_M
L_tank = g("tank_length_ft", 0) * FT_TO_M  # 0 = auto

# Initial conditions
V_liquid_0 = g("initial_liquid_volume_gal", 6500) * GAL_TO_M3
P_atm = g("ambient_pressure_psia", 14.696) * PSI_TO_PA
P_tank_0_gauge = g("initial_tank_pressure_psig", 0.0) * PSI_TO_PA
P_tank_0 = P_atm + P_tank_0_gauge
T_gas_0 = g("gas_temperature_C", 20.0) + 273.15

# Pressure limits
P_max_gauge = g("max_tank_pressure_psig", 25.0) * PSI_TO_PA
P_relief_gauge = g("relief_valve_pressure_psig", 27.5) * PSI_TO_PA
Cd_relief = g("relief_valve_Cd", 0.62)
D_relief = g("relief_valve_diameter_in", 1.0) * IN_TO_M

# Air supply
air_scfm = g("air_supply_scfm", 19.0)
mdot_air_max = air_scfm * SCFM_TO_M3S * P_STD / (R_AIR * T_STD)

# Compressor curve
c_clearance = g("compressor_clearance", 0.0)  # 0=plant_air, 0.02=rotary_vane, 0.04=reciprocating

# Liquid
rho_L = g("liquid_density_kg_m3", 1000.0)
mu_L = g("liquid_viscosity_cP", 100.0) * CP_TO_PAS

# Valve
D_valve = g("valve_diameter_in", 3.0) * IN_TO_M
K_valve_open = g("valve_K_open", 0.2)
u_valve = g("valve_opening_fraction", 1.0)

# Pipe segment 1
D_pipe1 = g("pipe1_diameter_in", 3.0) * IN_TO_M
L_pipe1 = g("pipe1_length_ft", 25.0) * FT_TO_M
eps_pipe1 = g("pipe1_roughness_mm", 0.01) * MM_TO_M
K_pipe1 = g("pipe1_K_minor", 1.0)

# Pipe segment 2
D_pipe2 = g("pipe2_diameter_in", 3.0) * IN_TO_M
L_pipe2 = g("pipe2_length_ft", 25.0) * FT_TO_M
eps_pipe2 = g("pipe2_roughness_mm", 0.01) * MM_TO_M
K_pipe2 = g("pipe2_K_minor", 1.0)

# Pipe segment 3 (inactive by default: L=0)
D_pipe3 = g("pipe3_diameter_in", 3.0) * IN_TO_M
L_pipe3 = g("pipe3_length_ft", 0.0) * FT_TO_M
eps_pipe3 = g("pipe3_roughness_mm", 0.01) * MM_TO_M
K_pipe3 = g("pipe3_K_minor", 0.0)

# Pipe segment 4 (inactive by default: L=0)
D_pipe4 = g("pipe4_diameter_in", 3.0) * IN_TO_M
L_pipe4 = g("pipe4_length_ft", 0.0) * FT_TO_M
eps_pipe4 = g("pipe4_roughness_mm", 0.01) * MM_TO_M
K_pipe4 = g("pipe4_K_minor", 0.0)

# Pipe segment 5 (inactive by default: L=0)
D_pipe5 = g("pipe5_diameter_in", 3.0) * IN_TO_M
L_pipe5 = g("pipe5_length_ft", 0.0) * FT_TO_M
eps_pipe5 = g("pipe5_roughness_mm", 0.01) * MM_TO_M
K_pipe5 = g("pipe5_K_minor", 0.0)

# Elevation & receiver
dz_total = g("elevation_change_ft", 0.0) * FT_TO_M
P_receiver_gauge = g("receiver_pressure_psig", 0.0) * PSI_TO_PA
P_receiver = P_atm + P_receiver_gauge

# Minimum volume
V_liquid_min = g("min_liquid_volume_gal", 10.0) * GAL_TO_M3

# ── Build override map ──
overrides = {
    "V_tank": V_tank,
    "D_tank": D_tank,
    "L_tank": L_tank,
    "V_liquid_0": V_liquid_0,
    "P_atm": P_atm,
    "P_tank_0": P_tank_0,
    "T_gas_0": T_gas_0,
    "P_max_gauge": P_max_gauge,
    "P_relief_gauge": P_relief_gauge,
    "Cd_relief": Cd_relief,
    "D_relief": D_relief,
    "mdot_air_max": mdot_air_max,
    "c_clearance": c_clearance,
    "rho_L": rho_L,
    "mu_L": mu_L,
    "D_valve": D_valve,
    "K_valve_open": K_valve_open,
    "u_valve": u_valve,
    "D_pipe1": D_pipe1,
    "L_pipe1": L_pipe1,
    "eps_pipe1": eps_pipe1,
    "K_pipe1": K_pipe1,
    "D_pipe2": D_pipe2,
    "L_pipe2": L_pipe2,
    "eps_pipe2": eps_pipe2,
    "K_pipe2": K_pipe2,
    "D_pipe3": D_pipe3,
    "L_pipe3": L_pipe3,
    "eps_pipe3": eps_pipe3,
    "K_pipe3": K_pipe3,
    "D_pipe4": D_pipe4,
    "L_pipe4": L_pipe4,
    "eps_pipe4": eps_pipe4,
    "K_pipe4": K_pipe4,
    "D_pipe5": D_pipe5,
    "L_pipe5": L_pipe5,
    "eps_pipe5": eps_pipe5,
    "K_pipe5": K_pipe5,
    "dz_total": dz_total,
    "P_receiver": P_receiver,
    "V_liquid_min": V_liquid_min,
}

override_str = ",".join(f"{k}={v}" for k, v in overrides.items())
print(override_str)

# Also write SI values as JSON for logging
si_path = os.environ.get("SI_JSON_PATH", "/tmp/si_values_v2.json")
si = dict(overrides)
si["stop_time"] = g("stop_time_s", 7200)
si["output_interval"] = g("output_interval_s", 1.0)
with open(si_path, "w") as f:
    json.dump(si, f, indent=2)
