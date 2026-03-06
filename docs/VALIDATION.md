# VALIDATION

## Validation Strategy

This document defines sanity checks, parameter sensitivity tests, and a reference numeric example to validate the TankerTransfer simulation model.

---

## 1. Sanity Checks (Qualitative)

Each check verifies that the model responds correctly to parameter changes.

| # | Test | Parameter Changed | Expected Effect | Pass Criteria |
|---|------|------------------|-----------------|---------------|
| 1 | **Viscosity up → flow down** | `viscosity_cP`: 220 → 500 | Higher friction → lower Q → longer transfer time | Total transfer time increases |
| 2 | **Hose bigger → flow up** | `hose_ID_in`: 2.0 → 3.0 | Lower friction (v² drops) → higher Q | Transfer time decreases |
| 3 | **Air flow up → pressure rises faster** | `air_supply_scfm`: 19 → 40 | More gas mass → P_tank rises faster | Peak pressure reached sooner |
| 4 | **Backpressure up → flow down** | `receiver_backpressure_psig`: 0 → 10 | Reduced ΔP_available → lower Q | Transfer time increases |
| 5 | **Hose longer → flow down** | `hose_length_ft`: 50 → 100 | More friction length → higher ΔP_loss | Transfer time increases |
| 6 | **Elevation up → flow down** | `elevation_change_ft`: 0 → 10 | Hydrostatic head opposes flow | Transfer time increases |
| 7 | **Max pressure up → faster transfer** | `max_tank_pressure_psig`: 30 → 50 | Higher driving pressure → higher Q | Transfer time decreases |
| 8 | **Pressure limit works** | Any scenario | P_tank must never exceed max_tank_pressure + tolerance | max(P_tank) ≤ P_max + 0.5 psig |
| 9 | **Mass conservation** | Any scenario | V_transferred(end) + V_remaining(end) = V_liquid(0) | Error < 0.1% |
| 10 | **Pump-only has no tank pressure rise** | Scenario C | `air_split_to_tank = 0` → P_tank stays at atmospheric | P_tank ≈ P_ambient throughout |

---

## 2. Reference Numeric Example

### Input Parameters (Scenario A — Pressurize Only)

| Parameter | Value | Unit |
|-----------|-------|------|
| tanker_total_volume_gal | 4500 | gal |
| initial_fill_fraction | 0.90 | — |
| max_tank_pressure_psig | 30 | psig |
| ambient_pressure_psia | 14.7 | psia |
| temperature_C | 25 | °C |
| air_supply_scfm | 19 | SCFM |
| air_split_fraction_to_tank | 1.0 | — |
| air_split_fraction_to_pump | 0.0 | — |
| density_kg_m3 | 880 | kg/m³ |
| viscosity_cP | 220 | cP |
| hose_ID_in | 2.0 | in |
| hose_length_ft | 50 | ft |
| roughness_mm | 0.0 | mm |
| minor_loss_K_total | 5.0 | — |
| elevation_change_ft | 0.0 | ft |
| receiver_backpressure_psig | 0 | psig |
| stop_time_s | 7200 | s |

### Hand-Calculation Estimates

**Tank volumes:**
- Total: 4500 gal = 17.034 m³
- Liquid: 4050 gal = 15.331 m³
- Ullage: 450 gal = 1.703 m³

**Air mass flow:**
- 19 SCFM × 0.000471947 m³/s = 0.008967 m³/s (at standard conditions)
- ṁ_air = 0.008967 × 101325 / (287.05 × 288.15) = 0.01098 kg/s

**Initial state:**
- P_tank(0) = 14.7 psia = 101325 Pa
- m_gas(0) = 101325 × 1.703 / (287.05 × 298.15) = 2.017 kg

**Time to reach 30 psig (if no liquid exits):**
- P_max = (30 + 14.7) × 6894.76 = 308,168 Pa
- Need m_gas_max = 308168 × 1.703 / (287.05 × 298.15) = 6.131 kg
- Δm = 6.131 - 2.017 = 4.114 kg
- Time ≈ 4.114 / 0.01098 ≈ 375 seconds ≈ 6.2 minutes (upper bound, assumes no liquid exits)

**In reality:** Liquid exits as pressure builds, expanding the ullage volume. This means pressure rises more slowly than the upper bound. Transfer time will be much longer.

**Flow estimate at 30 psig steady state:**
- ΔP = (30 + 14.7 - 14.7) × 6894.76 = 206,843 Pa (30 psi)
- D = 2.0 in = 0.0508 m, A = π/4 × 0.0508² = 0.002027 m²
- L = 50 ft = 15.24 m
- For motor oil at 220 cP = 0.22 Pa·s, expect laminar flow
- Guess v = 1 m/s: Re = 880 × 1 × 0.0508 / 0.22 = 203 (laminar!)
- f = 64/203 = 0.3153
- Loss factor: f·L/D + ΣK = 0.3153 × 15.24/0.0508 + 5 = 94.6 + 5 = 99.6
- v = sqrt(2 × 206843 / (880 × 99.6)) = sqrt(413686/87648) = sqrt(4.72) = 2.17 m/s
- Check Re = 880 × 2.17 × 0.0508 / 0.22 = 441 → still laminar ✓
- Recompute: f = 64/441 = 0.1451, loss = 0.1451 × 300 + 5 = 48.5
- v = sqrt(2 × 206843 / (880 × 48.5)) = sqrt(9.69) = 3.11 m/s
- Iterate: Re = 880 × 3.11 × 0.0508 / 0.22 = 632
- f = 64/632 = 0.1013, loss = 0.1013 × 300 + 5 = 35.4
- v = sqrt(2 × 206843 / (880 × 35.4)) = sqrt(13.28) = 3.64 m/s
- Converges around v ≈ 3.5 m/s, Q ≈ 3.5 × 0.002027 = 0.00710 m³/s = 113 GPM

**Expected transfer time estimate:**
- Volume to transfer: 4050 gal ≈ 15.33 m³
- Steady-state Q ≈ 113 GPM (at max pressure, which takes time to reach)
- Lower bound: 4050/113 ≈ 36 minutes (if at constant max flow)
- Accounting for pressure ramp-up: expect 45–90 minutes total

### Expected Outputs

| Metric | Expected Range |
|--------|---------------|
| Peak tank pressure | ≤ 30.5 psig (controller tolerance) |
| Steady-state flow rate | 50–150 GPM (depends on friction convergence) |
| Total transfer time | 30–120 minutes |
| Final V_transferred | ≈ 4050 gal |
| Mass conservation error | < 0.1% |

---

## 3. Comparing Scenarios

| Metric | Scenario A | Scenario B | Scenario C |
|--------|-----------|-----------|-----------|
| Tank pressurized? | Yes (30 psig) | Yes (slower rise) | No (atmospheric) |
| Pump active? | No | Yes (9.5 SCFM) | Yes (19 SCFM) |
| Expected fastest? | Depends | May be fastest | If pump efficiency high |
| Pressure risk? | Max 30 psig | Max ~30 psig | None |

---

## 4. Validation Procedure

After running all 3 scenarios:

1. **Check mass conservation:** `V_transferred(end) + V_remaining(end) ≈ V_liquid(0)` for each run
2. **Check pressure limit:** `max(P_tank_psig) ≤ 30.5` for Scenarios A and B
3. **Check Scenario C pressure:** `max(P_tank_psig) ≈ 0` (atmospheric)
4. **Check monotonicity:** `V_transferred` must be monotonically non-decreasing
5. **Check flow non-negative:** `Q_out ≥ 0` at all times
6. **Run sanity checks** from Section 1 by varying one parameter at a time
7. **Compare hand calculation** from Section 2 with Scenario A output

---

## 5. Known Limitations for V1

| Limitation | Impact | Severity |
|-----------|--------|----------|
| No thermal model | Small error in gas pressure (~5%) | Low |
| Simplified AODD pump | May over/underestimate pump flow | Medium |
| No manufacturer pump curve | Scenario B/C results approximate | Medium |
| No two-phase at tank bottom | Can't simulate last ~5% of liquid | Low |
| Smooth controller | Small overshoot possible (~0.5 psig) | Low |

---

## 6. V2.1 Validation — Tier 1 + Tier 2 (2026-03-06)

### 6a. Backward Compatibility

Verified that v2.1 changes produce identical results when new features are inactive:
- **Non-Newtonian (n=1.0):** 0.000% difference from pre-change baseline
- **Two-phase (D_outlet=3"):** No effect until last ~90 gal of 6,500 gal load

### 6b. Baseline Comparison (5 Products — Before vs After)

Run with identical inputs on v2.0 (before) and v2.1 (after all Tier 1+2 changes):

| Product | μ (cP) | Before (min) | After (min) | Δ Time | Status |
|---------|--------|-------------|------------|--------|--------|
| OCD | 0.6 | 47.0 | 47.6 | +1.2% | PASS |
| Ethylene Glycol | 16.1 | 48.0 | 48.6 | +1.3% | PASS |
| Resin Solution | 500 | 57.2 | 58.5 | +2.4% | PASS |
| Tall Oil Rosin | 5000 | 110.1 | 114.5 | +4.0% | FAIL (>60 min) |
| Perchloroethylene | 9900 | 163.2 | 179.1 | +9.7% | FAIL (>60 min) |

**Observation:** Higher-viscosity products show larger corrections — expected because the 3-segment K-fittings layout adds more realistic friction losses. No PASS/FAIL status changes.

### 6c. Uncertainty Study (RSS per White Eq. E.1)

45 simulations, 7 parameters, central finite-difference:

| Product | Base Time | RSS ± | % | Dominant Factor |
|---------|-----------|-------|---|----------------|
| OCD (0.6 cP) | 47.6 min | ±2.62 min | 5.5% | SCFM (63%) |
| Resin Solution (500 cP) | 58.5 min | ±3.26 min | 5.6% | SCFM (48%), μ (23%) |
| Tall Oil Rosin (5000 cP) | 114.5 min | ±8.43 min | 7.4% | μ (62%), D (18%) |

**Interpretation:** Low-viscosity products are compressor-limited (SCFM dominates). High-viscosity products are friction-limited (viscosity and diameter dominate).

### 6d. Non-Newtonian Verification

| Test | n | Expected | Result |
|------|---|----------|--------|
| Newtonian baseline | 1.0 | μ_eff = μ_L always | ✅ 0.000% difference |
| NIPOL latex (shear-thin) | 0.4 | Faster than Newtonian | ✅ 48.0 vs 51.7 min (7% faster) |

### 6e. Two-Phase Verification

| Time (min) | h_liquid (in) | f_two_phase | Description |
|-----------|--------------|-------------|-------------|
| 0 | 64.6 | 1.000 | Full tank, pure liquid |
| 46.0 | 3.5 | 1.000 | Near end, still pure |
| 47.0 | 2.91 | 0.997 | Two-phase onset |
| 47.5 | 1.5 | 0.500 | Half air entrainment |
| 48.0 | 0.14 | 0.007 | Effectively empty |

### 6f. Textbook Verification

All model equations verified against Frank White, *Fluid Mechanics*:
- Appendix E: Uncertainty propagation Eq. E.1 / E.2
- Chapter 6: Darcy-Weisbach, Swamee-Jain, K-fittings
- Equation sheet photos verified by user
