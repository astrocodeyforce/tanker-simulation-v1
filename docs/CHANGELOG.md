# CHANGELOG

All notable changes to this project will be documented in this file.

---
## [2.1.0] — 2026-03-06

### Phase: Physics Model Tier 1 + Tier 2 Improvements

#### Summary

Implemented 4 physics upgrades (2 Tier 1 + 2 Tier 2) to the TankerTransferV2 model,
validated against textbook (Frank White, *Fluid Mechanics* — Appendix E, Eq. E.1/E.2),
with full baseline comparison and uncertainty quantification.

#### Tier 1A — K-Fittings Realism (3-Segment Piping Layout)

Changed from 1 pipe segment (L=20ft, K=2.5) to a realistic 3-segment layout:

| Segment | Length | K_minor | Description |
|---------|--------|---------|-------------|
| Seg 1 — Nozzle | 1 ft | 0.50 | Tank outlet nozzle (entrance loss) |
| Seg 2 — Hose | 20 ft | 0.50 | Standard 20-ft discharge hose (cam-lock couplings) |
| Seg 3 — Customer | 1 ft | 2.10 | Customer piping (90° elbow + tee + exit loss) |
| **Total** | **22 ft** | **3.10** | Plus valve K=0.20 |

Impact: Low-viscosity +1%, high-viscosity up to +9.7% longer (more realistic).

#### Tier 1B — Uncertainty Study (RSS per White Eq. E.1)

- **45 simulations** (3 products × 7 parameters × 2 directions + 3 base cases)
- Central finite-difference sensitivity analysis
- 7 uncertainty parameters: μ (±15%), D (±2%), SCFM (±5%), V (±3%), ρ (±2%), K (±20%), Δz (±0.5ft)

| Product | Base Time | RSS Uncertainty | Dominant Parameter |
|---------|-----------|----------------|-------------------|
| OCD (0.6 cP) | 47.6 min | ±2.62 min (5.5%) | SCFM (63%) |
| Resin Solution (500 cP) | 58.5 min | ±3.26 min (5.6%) | SCFM (48%), then μ (23%) |
| Tall Oil Rosin (5000 cP) | 114.5 min | ±8.43 min (7.4%) | μ (62%), then D (18%) |

Results saved to `data/uncertainty_results_20260306_171656.json`.

New script: `scripts/uncertainty_study.py`

#### Tier 2A — Non-Newtonian Rheology (Power-Law Model)

Added power-law viscosity model to all pipe segments:

$$\mu_{eff} = \mu_L \cdot \left(\frac{8v}{D}\right)^{n-1}$$

- New parameter: `n_power_law` (default 1.0 = Newtonian)
- 6 new algebraic variables: `mu_eff_valve`, `mu_eff_pipe1`–`mu_eff_pipe5`
- Shear rate floored at 0.01 s⁻¹ to prevent singularity
- **Backward compatibility verified**: n=1.0 produces 0.000% difference from pre-change results
- Non-Newtonian test: NIPOL latex (n=0.4) → 48.0 min vs 51.7 min Newtonian (7% faster, shear-thinning)

Files changed: `TankerTransferV2.mo`, `yaml_to_override_v2.py`, `fleet_batch_sim.py`, `export_results_v2.py`

#### Tier 2B — Two-Phase End-of-Unload

Models air entrainment when liquid level drops below the outlet nozzle:

$$f_{2\phi} = 3s^2 - 2s^3, \quad s = \frac{h_{liquid}}{D_{outlet}}$$

- New parameter: `D_outlet` (default 3 in = same as valve)
- `f_two_phase` multiplies the driving pressure: `dP_drive × f_two_phase = dP_loss_total`
- Only affects last ~90 gal of 6,500 gal load (1.4%)
- Verified: onset at t=47.0 min (h=2.91″, f=0.997), at cutoff h=0.14″ (f=0.007)

#### Final Comparison (5 Products — Before vs After Tier 1+2)

| Product | Baseline | Final | Δ Time | Δ Flow |
|---------|----------|-------|--------|--------|
| OCD (0.6 cP) | 47.0 min | 47.6 min | +1.2% | −2.1% |
| Ethylene Glycol (16.1 cP) | 48.0 min | 48.6 min | +1.3% | −2.3% |
| Resin Solution (500 cP) | 57.2 min | 58.5 min | +2.4% | −6.2% |
| Tall Oil Rosin (5000 cP) | 110.1 min | 114.5 min | +4.0% | −6.8% |
| Perchloroethylene (9900 cP) | 163.2 min | 179.1 min | +9.7% | −11.2% |

No PASS/FAIL status changes. Higher-viscosity products show larger corrections (expected — more friction-sensitive).

#### Dashboard Updates

- **New inputs**: Power-Law Index (n) on Liquid tab, Outlet Nozzle Diameter on Discharge tab
- **New engineering charts**: Effective Viscosity (μ_eff vs time), Two-Phase Factor (f_two_phase)
- **Presets updated**: All 3 presets now use 3-segment piping layout with correct K values
- **YAML generator**: Writes `n_power_law` and `outlet_diameter_in` to config files
- **System Info**: Updated model description with non-Newtonian, two-phase, compressor curve
- **Reference table**: Power-law index (n) values for common liquid types

#### New/Modified Files

| File | Change |
|------|--------|
| `modelica/TankerTransferV2.mo` | ~470 lines — added n_power_law, D_outlet, mu_eff_*, f_two_phase |
| `scripts/yaml_to_override_v2.py` | Added n_power_law, D_outlet mappings |
| `scripts/fleet_batch_sim.py` | Updated to 3-segment piping layout |
| `scripts/export_results_v2.py` | 46 columns (added mu_eff_*, f_two_phase) |
| `scripts/uncertainty_study.py` | **New** — RSS uncertainty propagation |
| `scripts/compare_baseline_final.py` | **New** — before/after comparison report |
| `python/dashboard.py` | New inputs, charts, presets, YAML gen, system info |

#### Git

- Commit `e777681` — v2.1 physics (Tier 1+2: K-fittings, uncertainty, non-Newtonian, two-phase)
- Commit `6dd8754` — Dashboard updates (plots, inputs, presets)
- Pushed to `main` at `https://github.com/astrocodeyforce/tanker-simulation-v1.git`

---
## [2.0.0] — 2026-02-21/22

### Phase: Comprehensive Parametric Study & Production Dashboard

#### Parametric Sweep Engine (1,530 Total Simulations — Zero Failures)

| Sweep | Variable(s) | Sims | Script |
|-------|-------------|------|--------|
| A | Liquid Volume (2000–7000 gal) | 50 | `run_parametric_sweep.sh` |
| B | Tank Pressure (0–30 psig) | 50 | `run_parametric_sweep.sh` |
| C | Gas Temperature (−10–50°C) | 50 | `run_parametric_sweep.sh` |
| D | Compressor SCFM (5–100) | 50 | `run_parametric_sweep.sh` |
| E | Hose Diameter × SCFM (2D) | 100 | `run_hose_sweep.sh` |
| F | Viscosity (1–2000 cP) | 50 | `run_viscosity_sweep.sh` |
| G | Viscosity × Compressor (2D) | 100 | `run_visc_scfm_sweep.sh` |
| H | 5D Mega Combo (visc × scfm × diam × vol × press) | 1,080 | `run_mega_sweep.sh` |

#### Key Findings — ANOVA (from 1,080 Sweep H simulations)
- Viscosity: **32.4%** of variance — #1 factor
- Compressor SCFM: **30.1%** — #2 factor
- Hose diameter: **19.8%** — #3 factor
- Liquid volume: **3.6%** — minor
- Initial pressure: **0.2%** — **negligible; 0 psig always wins**

#### Pressure Verdict
- **Pre-pressurizing the tank HURTS in every combination tested.**
- 0 psig beats 10 psig beats 22 psig across all 360 matched pairs.
- The compressor time wasted pressurizing the headspace is never recovered.

#### Three Recommended Solutions (vs current 3"/19 SCFM baseline at 6000 gal, 500 cP)
| Solution | Config | Time | Improvement | Cost |
|----------|--------|------|-------------|------|
| 1 | 3" hose + 35 SCFM | 43.4 min | −33% | $2–4K |
| 2 | 4" hose + 35 SCFM | 30.8 min | −53% | $3.5–6K |
| 3 | 4" hose + 50 SCFM | 23.9 min | −63% | $5–9K |

#### Extreme Cases
| Scenario | Config | Time | Flow |
|----------|--------|------|------|
| Dream (fastest) | 1 cP, 64 SCFM, 5", 4000 gal, 0 psig | 9.4 min | 426 GPM avg |
| Nightmare (slowest) | 2000 cP, 19 SCFM, 3", 6500 gal, 22 psig | 108.1 min | 63 GPM avg |
| Ratio | | **11.5× slower** | |

#### Master Excel Report
- ✅ `data/parametric_sweeps/Master_Sweep_Report.xlsx` — 113 KB, 9 sheets
- Sheets: Executive Summary + Sweeps A through H
- Executive Summary includes: ANOVA table, pressure verdict, solution comparison, % improvements

#### Dashboard Enhancements
- ✅ **Company logo support** — sidebar displays logo from `data/assets/logo.png`
- ✅ **Logo upload** — System Info page includes drag-and-drop file uploader
- ✅ **Pre-pressurization time calculator** — when Starting Pressure > 0 psig:
  - Calculates time to pump air from 0 → target pressure using ideal gas law
  - Formula: `headspace_ft³ × (target_psig / 14.696) / SCFM`
  - Shows live estimate above the Run button using actual SCFM value
  - Adds "Pressurize Time" and "Total Realistic Time" to results summary
- ✅ Uses **dynamic SCFM** from the Air Supply tab (not hardcoded)

#### New Scripts
- ✅ `scripts/run_parametric_sweep.sh` — Sweeps A–D (single variable, 50 sims each)
- ✅ `scripts/run_hose_sweep.sh` — Sweep E (diameter × SCFM grid)
- ✅ `scripts/run_viscosity_sweep.sh` — Sweep F (viscosity 1–2000 cP)
- ✅ `scripts/run_visc_scfm_sweep.sh` — Sweep G (viscosity × SCFM grid)
- ✅ `scripts/run_mega_sweep.sh` — Sweep H (5D grid, 1,080 combinations)
  - 5 nested loops: viscosity × compressor × diameter × volume × pressure
  - Analytical pre-pressurization time: `headspace_scf × P_psig/14.696 / SCFM`
  - Total time = pressurize_time + valve_transfer_time
- ✅ `scripts/build_master_report.py` — Generates 9-sheet Excel workbook from all CSVs
- ✅ `scripts/upload_logo_server.py` — One-shot HTTP upload server for company logo

#### Data Files
- ✅ `data/parametric_sweeps/A_liquid_volume.csv` — 50 rows
- ✅ `data/parametric_sweeps/B_tank_pressure.csv` — 50 rows
- ✅ `data/parametric_sweeps/C_gas_temperature.csv` — 50 rows
- ✅ `data/parametric_sweeps/D_compressor_scfm.csv` — 50 rows
- ✅ `data/parametric_sweeps/E_hose_diameter_multi.csv` — 100 rows
- ✅ `data/parametric_sweeps/F_viscosity.csv` — 50 rows
- ✅ `data/parametric_sweeps/G_visc_scfm_combo.csv` — 100 rows
- ✅ `data/parametric_sweeps/H_mega_combo.csv` — 1,080 rows (84.5 KB)
- ✅ `data/parametric_sweeps/Master_Sweep_Report.xlsx` — 113 KB, 9 sheets
- ✅ `data/assets/logo.png` — Company logo (writable mount)

---
## [1.0.0] — 2026-02-20

### Phase: V2 Realistic Model — Full Rebuild

#### Physics Model (TankerTransferV2.mo)
- ✅ Horizontal cylindrical tank geometry (DOT-407) with algebraic liquid-level solve
- ✅ Multi-segment pipe network: valve + 2 pipe segments in series
- ✅ Smooth friction factor: cubic smoothstep blend (laminar ↔ turbulent, Re 2000–4000)
- ✅ Swamee-Jain explicit turbulent friction (replaces iterative Colebrook)
- ✅ Valve K-model with configurable opening fraction
- ✅ Pressure relief valve: subsonic orifice model (Cd, D_relief configurable)
- ✅ Compressor soft ramp-down controller (5 kPa band near P_max)
- ✅ 30 equations, 30 variables, 2 ODE states — compiles clean
- ✅ Verified: baseline (laminar), solvent (turbulent Re~149k), coating (pressure-capped)

#### Scenario Configs
- ✅ `config/v2_baseline.yaml` — Latex emulsion, 1050 kg/m³, 100 cP, 3" pipe
- ✅ `config/v2_solvent.yaml` — Solvent, 850 kg/m³, 1 cP, turbulent flow test
- ✅ `config/v2_coating.yaml` — Thick coating, 1200 kg/m³, 500 cP, 2" pipe, 3 ft elevation

#### Pipeline Scripts
- ✅ `scripts/yaml_to_override_v2.py` — YAML → SI override string (gal→m³, psig→Pa, cP→Pa·s, etc.)
- ✅ `scripts/run_scenario_v2.sh` — 5-step pipeline: parse → create dir → compile+simulate → export → log
- ✅ `scripts/export_results_v2.py` — Extract 30 variables from OpenModelica CSV
- ✅ `scripts/run_app_v2.sh` — Master wrapper: guard snapshot → all scenarios → guard verify
- ✅ `scripts/analyze_csv.py` — Quick time-series analysis tool

#### Dashboard (V2 Compatible)
- ✅ `python/dashboard.py` rewritten with 4 view modes:
  - Individual Charts (pressure, flow, volume remaining, volume transferred)
  - Comparison Overlay (multi-run on same axes)
  - System Flow Diagram (animated schematic)
  - Engineering Detail (pressure drops, Reynolds, liquid level, air mass flow)
- ✅ Backward-compatible with V1 runs via column name mapping
- ✅ V1 dashboard backed up as `python/dashboard_v1.py`

#### Documentation
- ✅ `docs/MODEL_MATH.md` rewritten for V2 equations (17 sections)
- ✅ `docs/APPLICATION_SPEC.md` rewritten for V2 parameters and scenarios
- ✅ `docs/APP_ARCHITECTURE.md` updated for V2 pipeline
- ✅ `docs/CHANGELOG.md` updated

#### Verification Results
| Scenario | Peak Q (GPM) | Peak P (psig) | Re regime | Unload time |
|----------|-------------|---------------|-----------|-------------|
| Baseline (latex) | 134.9 | 13.7 | Laminar (~1200) | ~50 min |
| Solvent | 166.3 | 4.6 | Turbulent (~149k) | ~50 min |
| Coating | 49.2 | 25.1 (cap hit) | Laminar | ~120 min |

#### Guard Check
- ✅ Full pipeline run with guard snapshot/verify — no production containers affected

---
## [0.0.1] — 2026-02-20

### Phase: Environment Initialization

#### Added
- ✅ Project directory structure created at `/opt/sim-lab/truck-tanker-sim-env/`
- ✅ Documentation system created (`docs/` directory with all planning files)
- ✅ Logging system created (`logs/` directory)
- ✅ Isolation rules defined in `RISK_AND_ISOLATION.md`
- ✅ System architecture documented with ASCII diagrams
- ✅ Validation checklist defined
- ✅ Runbook created with operational procedures
- ✅ Assumptions documented and verified

#### Not Yet Done
- 🔲 No containers created yet
- 🔲 No images pulled yet
- 🔲 No simulations run yet
- 🔲 Baseline snapshot pending

---

## [0.0.2] — 2026-02-20

### Phase: Baseline Snapshot & Docker Environment

#### Added
- ✅ Baseline Docker state snapshot captured (`_guard/`)
- ✅ `docker-compose.yml` created with full isolation
- ✅ `.env` file with COMPOSE_PROJECT_NAME=simlab
- ✅ HelloWorld Modelica model created
- ✅ Simulation runner script created
- ✅ Python visualization script created
- ✅ Guard integrity check script created
- ✅ Master execution workflow script created

#### Security
- ✅ Zero ports published
- ✅ Dedicated network (simlab_network)
- ✅ No external networks
- ✅ Bind mounts only (no named Docker volumes)
- ✅ No privileged mode

---

## [0.1.0] — 2026-02-20

### Phase: Application Implementation (TankerTransfer)

#### Documentation
- ✅ `docs/APPLICATION_SPEC.md` — Purpose, scenarios, engineering decisions
- ✅ `docs/REQUIREMENTS.md` — Functional and non-functional requirements, input spec
- ✅ `docs/APP_ARCHITECTURE.md` — Component architecture, data flow, directory layout
- ✅ `docs/MODEL_MATH.md` — Full equation derivations, unit conversions, assumptions
- ✅ `docs/VALIDATION.md` — Sanity checks, reference numeric example, comparison plan

#### Physics Model
- ✅ `modelica/TankerTransfer.mo` — Complete Modelica model with:
  - Ideal gas ullage dynamics
  - Liquid mass balance
  - Darcy-Weisbach friction (laminar/turbulent/transition)
  - Swamee-Jain explicit turbulent friction factor
  - AODD pump simplified model
  - Soft pressure limit controller (30 psig max)
  - All parameters configurable via -override

#### Scenario Configs
- ✅ `config/scenario_A_pressurize_only.yaml` — All air to tank (f_tank=1.0)
- ✅ `config/scenario_B_split_air.yaml` — Split 50/50 (f_tank=0.5, f_pump=0.5)
- ✅ `config/scenario_C_pump_only.yaml` — All air to pump (f_pump=1.0)

#### Scripts & Tools
- ✅ `scripts/run_scenario.sh` — YAML→override conversion, compile, simulate, export
- ✅ `scripts/export_results.py` — Robust CSV/MAT result extraction
- ✅ `scripts/run_app.sh` — Master wrapper: all scenarios + plots + guard + logs
- ✅ `python/plot_results.py` — 4-panel PNG visualization
- ✅ `python/make_report.py` — Comparison report (text + HTML)

#### Docker Compose Updates
- ✅ Added `openmodelica-runner` service (application simulation)
- ✅ Added `python-plotter` service (application visualization)
- ✅ Added resource limits: cpus=1.0, memory=1g on all services
- ✅ Legacy services (openmodelica, python-viz) preserved for HelloWorld

#### Security (Unchanged)
- ✅ Zero ports published
- ✅ Dedicated network (simlab_network) — no external
- ✅ Bind mounts only
- ✅ COMPOSE_PROJECT_NAME=simlab
- ✅ Resource limits prevent production starvation
- ✅ Guard check unchanged

---

## [0.2.0] — 2026-02-20

### Phase: Interactive Visualization Dashboard

#### Added
- ✅ `python/dashboard.py` — Streamlit + Plotly interactive web dashboard
- ✅ `python/requirements.txt` — Python dependencies (streamlit, plotly, pandas)
- ✅ `docs/DASHBOARD.md` — Secure access instructions (SSH tunnel)
- ✅ `visual-dashboard` Docker Compose service

#### Documentation Updates
- ✅ `docs/APPLICATION_SPEC.md` — Added Visualization Strategy section
- ✅ `docs/APP_ARCHITECTURE.md` — Added Component E: Visualization Dashboard Layer
- ✅ `docs/REQUIREMENTS.md` — Added FR-7 (interactive visualization), NFR-5 (port safety)
- ✅ `docs/RISK_AND_ISOLATION.md` — Added Port Exposure Strategy section
- ✅ `docs/RUNBOOK.md` — Added dashboard start/stop/access instructions

#### Security
- ✅ Localhost-only port binding: `127.0.0.1:8501:8501`
- ✅ No public exposure — SSH tunnel required
- ✅ No host network mode
- ✅ Dedicated container with resource limits (CPU: 1.0, Memory: 1 GB)
- ✅ Existing isolation guarantees preserved
- ✅ Guard check still valid (dashboard container excluded from guard)
