# APPLICATION ARCHITECTURE

## Overview

The application is a **config-driven, headless simulation pipeline** with five components:

```
┌──────────────┐      ┌────────────────────┐      ┌──────────────────┐
│  YAML Config │─────►│  YAML→Override      │─────►│  Override String  │
│  (inputs)    │      │  yaml_to_override   │      │  (SI units)       │
└──────────────┘      │  _v2.py             │      └────────┬─────────┘
                      └────────────────────┘               │
                                                           ▼
                      ┌────────────────────┐      ┌────────┴─────────┐
                      │  Run Output Dir    │◄─────│  Scenario Runner  │
                      │  data/runs/<ts>/   │      │  run_scenario_v2  │
                      │  • outputs.csv     │      │  .sh              │
                      │  • run_log.json    │      │  (compile→sim→    │
                      └────────┬───────────┘      │   export)         │
                               │                  └──────────────────┘
                      ┌────────┴───────────┐
                      │  Streamlit+Plotly   │
                      │  Dashboard          │
                      │  (dashboard.py)     │
                      └────────────────────┘
```

---

## Component A: Modelica Core Model (Physics)

**File:** `modelica/TankerTransferV2.mo`

### Submodels

| Block | Responsibility |
|-------|---------------|
| **Horizontal Cylinder Geometry** | Algebraic liquid-level solve: $V_{liquid} = L \cdot A_{cross}(h)$ in a horizontal cylinder |
| **Ullage Gas** | Ideal gas law (isothermal): $P = mRT/V_{gas}$. Tracks gas mass, pressure, volume. |
| **Liquid Inventory** | Volume balance: $dV_{liquid}/dt = -Q_L$. Tracks liquid remaining. |
| **Outlet Valve** | K-model with opening fraction: $K_{eff} = K_{open}/u^2$ |
| **Pipe Segment 1** | Darcy-Weisbach + minor losses. Auto laminar/turbulent via `smoothFriction()`. |
| **Pipe Segment 2** | Same as segment 1 with independent D, L, ε, K parameters. |
| **Compressor Controller** | Constant SCFM with soft ramp-down (5 kPa band) near $P_{max}$. |
| **Relief Valve** | Subsonic orifice model — opens above $P_{relief}$, discharges to atmosphere. |
| **Flow Equation** | Algebraic: $\Delta P_{drive} = \Delta P_{loss,total}$ solved implicitly by DAE solver. |

### Model Statistics

| Property | Value |
|----------|-------|
| Variables | 30 |
| Equations | 30 |
| ODE states | 2 ($m_{gas}$, $V_{liquid}$) |
| DAE index | 1 |
| Solver | DASSL |
| Tolerance | $10^{-6}$ |

### Model Parameters (Set From Config)

All 26 physics parameters are passed as Modelica `-override` flags. The YAML parser performs unit conversion to SI before injection.

---

## Component B: YAML Config Parser

**File:** `scripts/yaml_to_override_v2.py`

### Purpose

Reads a YAML config file with engineering units (gallons, psig, cP, inches, feet) and produces a Modelica override string in SI units.

### Unit Conversions

| From | To | Factor |
|:-----|:---|:-------|
| gal → m³ | × 0.00378541 |
| psig → Pa (abs) | (psig + 14.696) × 6894.76 |
| cP → Pa·s | × 0.001 |
| in → m | × 0.0254 |
| ft → m | × 0.3048 |
| mm → m | × 0.001 |
| SCFM → kg/s | × 5.782e-4 |
| °C → K | + 273.15 |

### Output Example

```
V_tank=26.49787,D_tank=1.905,L_tank=0.0,V_liquid_0=24.605,...,mu_L=0.1,...
```

---

## Component C: Scenario Runner

**File:** `scripts/run_scenario_v2.sh`

### 5-Step Pipeline

```
Step 1: Parse YAML config → generate override string (via yaml_to_override_v2.py)
Step 2: Create timestamped run directory: data/runs/<YYYYMMDD_HHMMSS_label>/
Step 3: Compile TankerTransferV2.mo and simulate with overrides (omc + OMPython)
Step 4: Export results to CSV (export_results_v2.py — 30 target variables)
Step 5: Write run_log.json (config, overrides, status, output paths)
```

### Execution Pattern

```bash
# Via Docker Compose (required — OpenModelica runs in container)
docker compose run --rm --entrypoint "" openmodelica-runner \
    bash /work/scripts/run_scenario_v2.sh /work/config/v2_baseline.yaml
```

**Note:** `--entrypoint ""` is required to avoid bash-in-bash collision from the compose entrypoint.

---

## Component D: Result Exporter

**File:** `scripts/export_results_v2.py`

### Exported Variables (30 total)

| Category | Variables |
|----------|----------|
| Time | `time` |
| Gas | `m_gas`, `V_gas`, `P_tank`, `P_gauge`, `P_tank_psig` |
| Liquid | `V_liquid`, `V_liquid_gal`, `h_liquid`, `A_cross_liquid` |
| Flow | `Q_L`, `Q_L_gpm`, `V_transferred`, `V_transferred_gal` |
| Velocities | `v_valve`, `v_pipe1`, `v_pipe2` |
| Reynolds | `Re_valve`, `Re_pipe1`, `Re_pipe2` |
| Friction | `f_pipe1`, `f_pipe2` |
| Pressure drops | `dP_drive`, `dP_head`, `dP_valve`, `dP_seg1`, `dP_seg2`, `dP_loss_total` |
| Air flows | `mdot_air_in`, `mdot_relief` |
| Valve | `K_valve_eff` |

### Output Format

- CSV with header row
- Handles OpenModelica's double-quoted headers
- One row per time step (typically 1-second intervals)

---

## Component E: Master Wrapper

**File:** `scripts/run_app_v2.sh`

### Workflow

```
1. Guard: Capture Docker state snapshot (--snapshot)
2. Loop: Run each V2 scenario config through the pipeline
3. Track: Count pass/fail per scenario
4. Guard: Verify Docker state unchanged (--verify)
5. Report: Summary (X passed, Y failed)
```

### Usage

```bash
# All scenarios
./scripts/run_app_v2.sh

# Single scenario (substring match)
./scripts/run_app_v2.sh v2_baseline
```

---

## Component F: Interactive Dashboard

**File:** `python/dashboard.py`

### View Modes

| Mode | Description |
|:-----|:-----------|
| **Individual Charts** | 4-panel: pressure, flow, volume remaining, volume transferred |
| **Comparison Overlay** | Select multiple runs, overlay on same axes per metric |
| **System Flow Diagram** | Animated schematic showing current state at selected time |
| **Engineering Detail** | Pressure drops (valve, seg1, seg2), Reynolds numbers, liquid level, air mass flow |

### Architecture

- Streamlit app running in `visual-dashboard` Docker container
- Scans `data/runs/` on each page load for available results
- Reads `outputs.csv` and `run_log.json` from each run directory
- Backward-compatible with V1 runs (maps old column names)

### Service Configuration

| Property | Value |
|----------|-------|
| Docker service | `visual-dashboard` |
| Container name | `simlab-dashboard` |
| Port binding | `127.0.0.1:8501:8501` (localhost only) |
| Access | SSH tunnel required |
| Resource limits | CPU: 1.0, Memory: 1 GB |

---

## Component G: Guard Check

**File:** `scripts/guard_check.sh`

Verifies that running simulations does NOT affect production Docker containers, networks, or volumes. Filters out `simlab`-prefixed items (our project) and compares before/after state.

---

## Component H: File Download Server

**File:** `python/file_server.py`

### Purpose

Persistent HTTP file server on port 8502 for special-case reports (pump analyses,
driver forms, engineering memos). **Completely separate** from the dashboard's
simulation PDF export feature.

### Architecture

- Python `http.server` with styled HTML directory listing
- Serves everything in `data/downloads/` — drop a file in, it's instantly available
- Auto-starts with Docker (`restart: unless-stopped`)
- Lightweight: 0.25 CPU, 128 MB RAM

### When to Use

| Use This (port 8502) | Use Dashboard (port 8501) |
|:----------------------|:-------------------------|
| One-off equipment analyses | Simulation run PDFs |
| Driver reference forms | Per-scenario chart exports |
| Engineering memos | Past results comparison |
| Any file you drop in `data/downloads/` | Auto-generated from sim data |

### Service Configuration

| Property | Value |
|----------|-------|
| Docker service | `file-server` |
| Container name | `simlab-file-server` |
| Port binding | `0.0.0.0:8502:8502` |
| Serve directory | `data/downloads/` |
| Resource limits | CPU: 0.25, Memory: 128 MB |

---

## Directory Layout

```
truck-tanker-sim-env/
├── config/
│   ├── v2_baseline.yaml          # Latex emulsion scenario
│   ├── v2_solvent.yaml           # Low-viscosity solvent scenario
│   ├── v2_coating.yaml           # High-viscosity coating scenario
│   ├── scenario_A_*.yaml         # (V1 legacy — preserved)
│   ├── scenario_B_*.yaml
│   └── scenario_C_*.yaml
├── modelica/
│   ├── TankerTransferV2.mo       # V2 realistic model
│   └── TankerTransfer.mo         # V1 model (preserved)
├── scripts/
│   ├── yaml_to_override_v2.py    # YAML → SI override string
│   ├── run_scenario_v2.sh        # V2 single-scenario pipeline
│   ├── export_results_v2.py      # CSV extraction (30 variables)
│   ├── run_app_v2.sh             # V2 master wrapper + guard
│   ├── analyze_csv.py            # Quick analysis tool
│   ├── guard_check.sh            # Docker state integrity check
│   ├── run_scenario.sh           # (V1 legacy)
│   ├── run_app.sh                # (V1 legacy)
│   └── export_results.py         # (V1 legacy)
├── python/
│   ├── dashboard.py              # V2 Streamlit+Plotly dashboard
│   ├── dashboard_v1.py           # V1 dashboard backup
│   ├── file_server.py            # Port 8502 file download server
│   ├── pump_report.py            # Pump analysis PDF generator
│   ├── plot_results.py           # Static PNG plots
│   └── requirements.txt          # Python deps (incl. kaleido==0.2.1)
├── data/
│   ├── downloads/                # Files served on port 8502
│   │   ├── Pump_Analysis_Report.pdf
│   │   ├── Driver_Unloading_Data_Form.pdf
│   │   └── Driver_Unloading_Sheet_V2.pdf
│   ├── assets/
│   │   └── logo.png
│   └── runs/
│       └── <YYYYMMDD_HHMMSS_label>/
│           ├── inputs.yaml
│           ├── outputs.csv       # 42-variable time series
│           └── run_log.json
├── docs/
│   ├── APPLICATION_SPEC.md
│   ├── APP_ARCHITECTURE.md
│   ├── MODEL_MATH.md
│   ├── CHANGELOG.md
│   ├── DASHBOARD.md
│   ├── VALIDATION.md
│   └── ... (other docs)
├── _guard/                       # Guard state snapshots
├── docker-compose.yml
└── .env
```

---

## Execution Flow

### Single Scenario

```bash
cd /opt/sim-lab/truck-tanker-sim-env
docker compose run --rm --entrypoint "" openmodelica-runner \
    bash /work/scripts/run_scenario_v2.sh /work/config/v2_baseline.yaml
```

### All Scenarios + Guard Check

```bash
cd /opt/sim-lab/truck-tanker-sim-env
./scripts/run_app_v2.sh
```

### Dashboard Access

```bash
# From local machine via SSH tunnel
ssh -L 8501:127.0.0.1:8501 user@your-vps-ip
# Then open http://localhost:8501 in browser
```

---

## Separation of Concerns

```
┌─────────────────────────┐      ┌─────────────────────────────┐
│   SIMULATION ENGINE     │      │   VISUALIZATION ENGINE      │
│                         │      │                             │
│  OpenModelica (omc)     │─CSV─►│  Streamlit + Plotly         │
│  run_scenario_v2.sh     │      │  dashboard.py               │
│  export_results_v2.py   │      │                             │
│                         │      │  Reads data/runs/ (read)    │
│  Writes data/runs/ (rw) │      │  Serves on 127.0.0.1:8501  │
└─────────────────────────┘      └─────────────────────────────┘
```

- Simulation engine **writes** results — no knowledge of the dashboard
- Visualization engine **reads** results — never modifies simulation data
- They share the `data/` bind mount but have no runtime coupling

---

## Isolation Guarantee

| Property | Value |
|----------|-------|
| COMPOSE_PROJECT_NAME | `simlab` |
| Published ports | `0.0.0.0:8501` (dashboard), `0.0.0.0:8502` (file server) |
| External networks | NONE |
| Volume strategy | Bind mounts only |
| Resource limits | CPU: 1.0, Memory: 1 GB per container |
| Guard check | Required before/after every run |
