# APPLICATION SPECIFICATION

## Purpose

A **dynamic, physics-based simulation tool** for air-displacement unloading of a DOT-407 horizontal cylindrical tanker truck. The system models pressurizing the tanker ullage with compressed air to push liquid out through a multi-segment discharge pipeline.

**Key design goals:**
- All parameters dynamic and configurable via YAML — test different chemicals, pipe sizes, compressor capacities
- Realistic geometry: horizontal cylinder with proper liquid-level model
- Full pipe network: valve + multi-segment piping with friction and minor losses
- Automatic laminar/turbulent friction regime switching
- Safety modeled: pressure cap controller + relief valve

---

## What the Simulator Quantifies

| Output | Unit | Description |
|--------|------|-------------|
| Flow rate vs time | GPM | Instantaneous liquid discharge rate |
| Tank pressure vs time | psig | Ullage gas pressure |
| Volume remaining vs time | gallons | Liquid still in the tanker |
| Volume transferred vs time | gallons | Cumulative liquid moved to receiver |
| Liquid level vs time | m | Height in horizontal cylinder |
| Reynolds number vs time | — | Flow regime indicator per pipe segment |
| Pressure drops vs time | Pa | Per-component (valve, pipe 1, pipe 2) |
| Air mass flow vs time | kg/s | Compressor in + relief out |

---

## Configurable Parameters

### Tank

| Parameter | Config Key | Unit | Default | Description |
|-----------|-----------|------|---------|-------------|
| Total volume | `tank.volume_gal` | gal | 7000 | Internal volume |
| Diameter | `tank.diameter_in` | in | 75 | DOT-407 standard |
| Length | `tank.length_ft` | ft | auto | Auto-calc from V, D |
| Initial fill | `tank.initial_fill_gal` | gal | 6500 | Starting liquid |
| Max pressure | `tank.max_pressure_psig` | psig | 25 | Pressure cap |
| Relief pressure | `tank.relief_pressure_psig` | psig | 27.5 | Relief setpoint |
| Relief diameter | `tank.relief_diameter_in` | in | 1.0 | Orifice size |
| Relief Cd | `tank.relief_Cd` | — | 0.62 | Discharge coefficient |

### Liquid

| Parameter | Config Key | Unit | Default | Description |
|-----------|-----------|------|---------|-------------|
| Density | `liquid.density_kg_m3` | kg/m³ | 1050 | Latex emulsion |
| Viscosity | `liquid.viscosity_cP` | cP | 100 | Dynamic viscosity |

### Air Supply

| Parameter | Config Key | Unit | Default | Description |
|-----------|-----------|------|---------|-------------|
| Compressor | `air.scfm` | SCFM | 19 | Air mass flow |

### Valve

| Parameter | Config Key | Unit | Default | Description |
|-----------|-----------|------|---------|-------------|
| Bore diameter | `valve.diameter_in` | in | 3.0 | Valve body size |
| K (fully open) | `valve.K_open` | — | 0.2 | Loss coefficient |
| Opening fraction | `valve.opening` | 0–1 | 1.0 | Throttle position |

### Pipe Network (per segment)

| Parameter | Config Key | Unit | Default | Description |
|-----------|-----------|------|---------|-------------|
| Diameter | `pipe_N.diameter_in` | in | 3.0 | Inner diameter |
| Length | `pipe_N.length_ft` | ft | 25 | Length |
| Roughness | `pipe_N.roughness_mm` | mm | 0.01 | Surface roughness |
| K (fittings) | `pipe_N.K_fittings` | — | 1.0–1.5 | Minor losses |

### Discharge

| Parameter | Config Key | Unit | Default | Description |
|-----------|-----------|------|---------|-------------|
| Elevation | `discharge.elevation_ft` | ft | 0 | Outlet → receiver rise |
| Receiver pressure | `discharge.receiver_pressure_psig` | psig | 0 | Backpressure |

### Simulation

| Parameter | Config Key | Unit | Default | Description |
|-----------|-----------|------|---------|-------------|
| Duration | `simulation.stop_time_s` | s | 5400 | Max simulation time |
| Intervals | `simulation.intervals` | — | 5400 | Output data points |

---

## Three V2 Scenarios

### Baseline — Latex Emulsion (100 cP)

- **File:** `config/v2_baseline.yaml`
- **Liquid:** 1050 kg/m³, 100 cP (latex paint/emulsion)
- **Pipe:** 3" × 25 ft × 2 segments
- **Flow regime:** Laminar (Re ≈ 1200)
- **Expected:** ~135 GPM peak flow, 13.7 psig peak pressure, ~50 min transfer

### Solvent — Low Viscosity (1 cP)

- **File:** `config/v2_solvent.yaml`
- **Liquid:** 850 kg/m³, 1 cP (solvent/water-like)
- **Pipe:** 3" × 25 ft × 2 segments
- **Flow regime:** Turbulent (Re ≈ 149,000)
- **Expected:** ~166 GPM peak flow, 4.6 psig peak pressure, ~50 min transfer

### Coating — High Viscosity (500 cP)

- **File:** `config/v2_coating.yaml`
- **Liquid:** 1200 kg/m³, 500 cP (thick industrial coating)
- **Pipe:** 2" × 30 ft × 2 segments, 3 ft elevation
- **Flow regime:** Laminar (Re very low)
- **Expected:** ~49 GPM peak flow, hits 25 psig pressure cap, ~120 min transfer

---

## Engineering Decisions This Tool Supports

| Question | How the Simulator Answers It |
|----------|------------------------------|
| **Is 19 SCFM enough for my product?** | Run with your liquid properties — see if transfer completes in acceptable time |
| **What pressure limit is needed?** | Sweep `max_pressure_psig`, compare flow rates and transfer times |
| **How does viscosity affect transfer?** | Compare baseline (100 cP) vs solvent (1 cP) vs coating (500 cP) |
| **What pipe size matters?** | Vary `pipe_N.diameter_in` — larger pipe = much less friction |
| **How does backpressure affect transfer?** | Increase `discharge.receiver_pressure_psig` — see flow reduction |
| **Does elevation matter?** | Increase `discharge.elevation_ft` — quantify head loss impact |
| **When does the pressure cap activate?** | Run coating scenario — pressure saturates at 25 psig |
| **Is the relief valve appropriately sized?** | Check `mdot_relief` in engineering detail view |
| **Should I pre-pressurize the tank?** | **No.** 1,080 simulations proved 0 psig always wins. Pressurization time is wasted. |
| **What's the best upgrade for my money?** | 3 solutions: 35 SCFM (−33%), 4"+35 SCFM (−53%), 4"+50 SCFM (−63%) |
| **What's the worst-case scenario?** | 2000 cP + 19 SCFM + 3" + 6500 gal = 108.1 min (1.8 hours) |
| **How long to pre-pressurize?** | Dashboard auto-calculates: `headspace_ft³ × (psig / 14.696) / SCFM` |

---

## Parametric Study Results (1,530 Simulations)

### Variable Importance (ANOVA — Sweep H, 1,080 sims)

| Variable | % Variance | Rank | Practical Impact |
|----------|-----------|------|------------------|
| Viscosity (1–2000 cP) | 32.4% | #1 | Cannot control — depends on product |
| Compressor SCFM (19–64) | 30.1% | #2 | **Best upgrade target** |
| Hose diameter (3"–5") | 19.8% | #3 | **Second-best upgrade** |
| Liquid volume (4000–6500 gal) | 3.6% | #4 | Depends on order size |
| Initial pressure (0–22 psig) | 0.2% | #5 | **Useless — never pre-pressurize** |

### Recommended Upgrades (at 6000 gal, 500 cP, 0 psig)

| Solution | Config | Transfer Time | vs Current | Est. Cost |
|----------|--------|--------------|------------|-----------|
| Current | 3" / 19 SCFM | 64.9 min | baseline | — |
| Solution 1 | 3" / 35 SCFM | 43.4 min | −33% | $2–4K |
| Solution 2 | 4" / 35 SCFM | 30.8 min | −53% | $3.5–6K |
| Solution 3 | 4" / 50 SCFM | 23.9 min | −63% | $5–9K |

### Extreme Bounds

| Scenario | Config | Time |
|----------|--------|------|
| Fastest possible | 1 cP, 64 SCFM, 5", 4000 gal, 0 psig | **9.4 min** |
| Slowest possible | 2000 cP, 19 SCFM, 3", 6500 gal, 22 psig | **108.1 min** |
| Range ratio | | **11.5×** |

---

## Constraints

| Constraint | Value | Rationale |
|-----------|-------|-----------|
| Max tank pressure | 25 psig (configurable) | DOT-407 regulatory limit |
| Relief valve | 27.5 psig (configurable) | Safety margin above operating |
| Air supply | 19 SCFM typical (parametric) | Field compressor capacity |
| Tank type | DOT-407 horizontal cylinder | Industry standard for chemical transport |
| Liquid | Any Newtonian fluid | Configurable ρ, μ |

---

## Technology Stack

| Component | Technology | Role |
|-----------|-----------|------|
| Physics engine | OpenModelica (v1.23.1) | DAE solver for dynamic model |
| Config → override | Python (yaml_to_override_v2.py) | YAML parsing + unit conversion |
| Result export | Python (export_results_v2.py) | CSV extraction (30 variables) |
| Visualization | Streamlit + Plotly (dashboard.py) | Interactive web dashboard |
| Configuration | YAML | Scenario parameters — edit config, not code |
| Execution | Docker Compose | Headless, isolated, reproducible |
| Guard | Bash script | Verify no production Docker state changes |

### Dashboard View Modes

| Mode | Description |
|------|-------------|
| Individual Charts | 4-panel view: pressure, flow, volume remaining, volume transferred |
| Comparison Overlay | Compare multiple runs on the same axes |
| System Flow Diagram | Animated schematic showing system state |
| Engineering Detail | Pressure drops, Reynolds numbers, liquid level, air mass flow |

---

## What This Is NOT

- **Not a CFD simulation** — 1D lumped-parameter model
- **Not a real-time controller** — simulates ahead of time
- **Not a non-Newtonian model** (yet) — uses constant μ (extensible to power-law)
- **Does not model thermal effects** — isothermal assumption
- **Does not model two-phase flow** — valid until tank is nearly empty
