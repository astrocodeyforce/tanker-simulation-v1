# REQUIREMENTS

## Functional Requirements

### FR-1: Three Simulation Scenarios

| ID | Requirement |
|----|-------------|
| FR-1.1 | **Scenario A (Pressurize Only):** All air pressurizes the tanker ullage. Liquid exits by gas pressure differential. |
| FR-1.2 | **Scenario B (Split Air):** Air is split between tank pressurization and AODD pump drive. Both mechanisms contribute to liquid transfer. |
| FR-1.3 | **Scenario C (Pump Only):** All air drives the AODD pump. Tank remains at atmospheric pressure. |

### FR-2: Config-Driven Execution

| ID | Requirement |
|----|-------------|
| FR-2.1 | All scenario parameters must be defined in a YAML config file. |
| FR-2.2 | Running a different scenario requires only changing which config file is passed — no code edits. |
| FR-2.3 | Config files must support all parameters listed in the Input Specification section below. |

### FR-3: Headless Docker Execution

| ID | Requirement |
|----|-------------|
| FR-3.1 | Simulations must run via `docker compose run --rm` with no GUI. |
| FR-3.2 | No ports may be published. |
| FR-3.3 | All output must be written to bind-mounted directories. |

### FR-4: Output Generation

| ID | Requirement |
|----|-------------|
| FR-4.1 | Each run must produce a CSV file with columns: `time`, `P_tank_psig`, `Q_out_gpm`, `V_liquid_gal`, `V_transferred_gal`. |
| FR-4.2 | Each run must produce PNG plots: tank pressure vs time, flow rate vs time, volume remaining vs time, cumulative transferred volume vs time. |
| FR-4.3 | Output must be organized in timestamped run folders under `data/runs/`. |

### FR-5: Run Logging

| ID | Requirement |
|----|-------------|
| FR-5.1 | Every run must produce a `run_log.json` containing: timestamp, scenario name, all input parameters, output file paths, and success/failure status. |
| FR-5.2 | A copy of the input config must be saved with each run as `inputs.yaml`. |

### FR-6: Convenience Execution

| ID | Requirement |
|----|-------------|
| FR-6.1 | A single `./scripts/run_app.sh` command must run all 3 scenarios, generate all plots, run guard check, and write logs. |
| FR-6.2 | Individual scenarios must also be runnable independently. |

### FR-7: Interactive Visualization Dashboard

| ID | Requirement |
|----|-------------|
| FR-7.1 | Must provide a browser-based interactive visualization of simulation results. |
| FR-7.2 | Dashboard must scan `data/runs/` and list all available simulation outputs. |
| FR-7.3 | Users must be able to select scenario outputs from a sidebar menu. |
| FR-7.4 | Must render interactive Plotly charts: Pressure vs Time, Flow vs Time, Volume Remaining vs Time, Transferred Volume vs Time. |
| FR-7.5 | Charts must support zoom, pan, and hover-to-inspect capabilities. |

---

## Non-Functional Requirements

### NFR-1: Isolation

| ID | Requirement |
|----|-------------|
| NFR-1.1 | `COMPOSE_PROJECT_NAME=simlab` must remain. |
| NFR-1.2 | No external Docker networks may be joined. |
| NFR-1.3 | No published ports. |
| NFR-1.4 | Guard check must pass after every run — no production containers/networks/volumes may change. |

### NFR-2: Resource Limits

| ID | Requirement |
|----|-------------|
| NFR-2.1 | Simulation containers should have CPU limits (recommended: 1.0 CPU). |
| NFR-2.2 | Simulation containers should have memory limits (recommended: 1 GB). |
| NFR-2.3 | Resource limits must prevent starving production containers. |

### NFR-3: Determinism

| ID | Requirement |
|----|-------------|
| NFR-3.1 | Same config inputs must produce same CSV outputs (within solver tolerance). |
| NFR-3.2 | Random seeds or non-deterministic operations are not allowed. |

### NFR-4: Maintainability

| ID | Requirement |
|----|-------------|
| NFR-4.1 | Physics model must be in Modelica (not hardcoded in scripts). |
| NFR-4.2 | Visualization must be separate from simulation. |
| NFR-4.3 | Adding a new scenario requires only a new YAML config file. |

### NFR-5: Dashboard Port Safety

| ID | Requirement |
|----|-------------|
| NFR-5.1 | Dashboard port MUST use localhost-only binding: `127.0.0.1:8501:8501`. |
| NFR-5.2 | Public port binding (e.g., `0.0.0.0:8501:8501`) is **FORBIDDEN**. |
| NFR-5.3 | Host network mode (`network_mode: host`) is **FORBIDDEN**. |
| NFR-5.4 | Dashboard must be accessible only via SSH tunnel. |

---

## Input Specification

Each scenario YAML config must support these parameter groups:

### Core Tank
| Parameter | Type | Unit | Default | Description |
|-----------|------|------|---------|-------------|
| `tanker_total_volume_gal` | float | gal | 4500 | Total tanker capacity |
| `initial_fill_fraction` | float | — | 0.90 | Fraction of tank initially filled with liquid |
| `max_tank_pressure_psig` | float | psig | 30 | Maximum allowable ullage pressure |
| `ambient_pressure_psia` | float | psia | 14.7 | Atmospheric pressure |
| `temperature_C` | float | °C | 25 | Ambient temperature (for gas law) |

### Air Supply
| Parameter | Type | Unit | Default | Description |
|-----------|------|------|---------|-------------|
| `air_supply_scfm` | float | SCFM | 19 | Total standard air supply rate |
| `air_split_fraction_to_tank` | float | — | varies | Fraction of air to tank pressurization (0–1) |
| `air_split_fraction_to_pump` | float | — | varies | Fraction of air to AODD pump (0–1) |

### Liquid Properties (Motor Oil)
| Parameter | Type | Unit | Default | Description |
|-----------|------|------|---------|-------------|
| `density_kg_m3` | float | kg/m³ | 880 | Liquid density |
| `viscosity_cP` | float | cP | 220 | Dynamic viscosity |

### Hose / Piping
| Parameter | Type | Unit | Default | Description |
|-----------|------|------|---------|-------------|
| `hose_ID_in` | float | inches | 2.0 | Internal diameter of transfer hose |
| `hose_length_ft` | float | feet | 50 | Total hose length |
| `roughness_mm` | float | mm | 0.0 | Pipe roughness (0 = smooth) |
| `minor_loss_K_total` | float | — | 5.0 | Sum of all minor loss coefficients |
| `elevation_change_ft` | float | feet | 0.0 | Height of receiver above tanker outlet (positive = uphill) |

### Receiving System
| Parameter | Type | Unit | Default | Description |
|-----------|------|------|---------|-------------|
| `receiver_backpressure_psig` | float | psig | 0 | Pressure at receiver inlet |

### AODD Pump (Scenarios B & C)
| Parameter | Type | Unit | Default | Description |
|-----------|------|------|---------|-------------|
| `pump_efficiency_gpm_per_scfm` | float | GPM/SCFM | 0.5 | Simplified pump conversion: GPM output per SCFM air input |

### Simulation Settings
| Parameter | Type | Unit | Default | Description |
|-----------|------|------|---------|-------------|
| `stop_time_s` | float | s | 7200 | Maximum simulation duration |
| `output_interval_s` | float | s | 1.0 | Time step for CSV output |
