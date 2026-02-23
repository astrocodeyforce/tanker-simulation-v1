# APPLICATION SPECIFICATION

## Purpose

We are building a **dynamic, physics-based simulation tool** for a truck tanker liquid transfer system used to move viscous liquids (motor oil) by either:

1. **Pressurizing tanker ullage** with compressed air to push liquid out
2. **Using an air-operated diaphragm pump (AODD)**
3. **Comparing mixed strategies** where air supply is split between tank pressurization and pump

---

## What the Simulator Quantifies

| Output | Unit | Description |
|--------|------|-------------|
| Flow rate vs time | GPM | Instantaneous liquid discharge rate |
| Tank pressure vs time | psig | Ullage gas pressure in the tanker |
| Transferred volume vs time | gallons | Cumulative liquid moved to receiver |
| Volume remaining vs time | gallons | Liquid still in the tanker |
| Total transfer time | seconds/minutes | Time to empty (or reach target) |

---

## Constraints

| Constraint | Value | Rationale |
|-----------|-------|-----------|
| Max tank pressure | 30 psig | Tanker structural/regulatory limit |
| Air supply | 19 SCFM typical | Available compressor capacity |
| Liquid | Motor oil (viscous) | High viscosity = significant friction losses |

---

## Engineering Decisions This Tool Supports

| Question | How the Simulator Answers It |
|----------|------------------------------|
| **Is 19 SCFM enough?** | Run Scenario A — see if transfer completes in acceptable time |
| **What pressure limit is required to hit a target transfer time?** | Sweep `max_tank_pressure_psig` in config, compare results |
| **When is pump better than air-pressurization?** | Compare Scenario A vs C total transfer times |
| **How does splitting air help?** | Scenario B shows combined strategy performance |
| **How do turbulent vs laminar conditions change outcomes?** | Vary hose diameter/viscosity — model auto-switches friction regime |
| **What hose size matters?** | Sweep `hose_ID_in` — larger hose = less friction |
| **How does backpressure affect transfer?** | Increase `receiver_backpressure_psig` — slower flow |

---

## Three Core Scenarios

### Scenario A — Pressurize Only
- All compressed air goes into the tanker ullage
- Liquid is pushed out by gas pressure alone
- `air_split_fraction_to_tank = 1.0`

### Scenario B — Split Air (Pressurize + Pump)
- Half the air pressurizes the tank, half drives the AODD pump
- Combined strategy
- `air_split_fraction_to_tank = 0.5`, `air_split_fraction_to_pump = 0.5`

### Scenario C — Pump Only
- All air drives the AODD pump
- Tank is not pressurized (atmospheric)
- `air_split_fraction_to_pump = 1.0`

---

## Technology Stack

| Component | Technology | Role |
|-----------|-----------|------|
| Physics engine | OpenModelica | ODE solver for dynamic tank/flow model |
| Visualization | Python (matplotlib) | Generate PNG plots |
| Configuration | YAML | Scenario parameters — edit config, not code |
| Execution | Docker Compose | Headless, isolated, reproducible |
| Guard | Bash script | Verify no production Docker state changes |

---

## Visualization Strategy

The application provides three tiers of result visualization:

| Tier | Component | Technology | Purpose |
|------|-----------|------------|---------|
| 1 | Headless Simulation Engine | OpenModelica | Produces raw CSV time-series data |
| 2 | Offline Plot Generator | Python + matplotlib | Generates static 4-panel PNG plots |
| 3 | **Interactive Web Dashboard** | Python + Streamlit + Plotly | Browser-based interactive exploration |

### Interactive Web Dashboard

**Purpose:** Provide real-time interactive visualization of simulation results without downloading files.

Capabilities:
- View pressure, flow, and volume curves with interactive zoom/pan
- Select and compare scenario outputs from a sidebar menu
- Hover over data points for precise values
- Access results from any SSH-tunneled browser session

**Access:** Localhost-only via SSH tunnel — see `docs/DASHBOARD.md` for instructions.

---

## What This Is NOT

- This is **not** a CFD simulation — we use 1D lumped-parameter models
- This is **not** a real-time controller — it simulates ahead of time
- This does **not** replace manufacturer pump curves — it uses simplified AODD models (upgradeable)
- This does **not** model thermal effects (isothermal assumption initially)
