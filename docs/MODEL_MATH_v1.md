# MODEL MATH

## Overview

This document describes the physics equations implemented in `TankerTransfer.mo`.
The model is **1D lumped-parameter** — no spatial gradients, single pressure/temperature per compartment.

---

## 1. System Schematic

```
         Compressed Air In
              │ ṁ_air_tank
              ▼
    ┌─────────────────────┐
    │     ULLAGE GAS       │  P_tank, V_gas, T
    │     (compressible)   │
    ├─────────────────────┤  ← liquid surface
    │     LIQUID (oil)     │  V_liquid, ρ_liq
    │                      │
    └──────────┬──────────┘
               │  Q_out (volumetric flow)
               ▼
    ┌─────────────────────┐
    │     HOSE / PIPE      │  L, D, ε, ΣK
    │   (friction losses)  │
    └──────────┬──────────┘
               │
               ▼
    ┌─────────────────────┐
    │     RECEIVER         │  P_receiver (constant)
    │   + elevation Δz     │
    └─────────────────────┘
```

Additionally, for Scenarios B and C, an AODD pump provides extra flow driven by `ṁ_air_pump`.

---

## 2. Gas Compressibility in Ullage (Ideal Gas Law)

### Assumption
- Gas behaves as ideal gas (air at moderate pressures ≤ 30 psig ≈ 3 atm absolute — ideal gas is reasonable)
- Isothermal process (temperature constant at T)

### Equations

The total gas mass in the ullage:

$$\frac{dm_{gas}}{dt} = \dot{m}_{air,tank}$$

where $\dot{m}_{air,tank}$ is the mass flow rate of compressed air entering the ullage.

The gas volume equals the tank void space:

$$V_{gas}(t) = V_{tank,total} - V_{liquid}(t)$$

Pressure from ideal gas law:

$$P_{tank}(t) = \frac{m_{gas}(t) \cdot R_{air} \cdot T}{V_{gas}(t)}$$

where:
- $R_{air} = 287.05$ J/(kg·K) — specific gas constant for air
- $T$ = temperature in Kelvin
- $P_{tank}$ is **absolute** pressure in Pascals

### Air Supply Conversion (SCFM → kg/s)

Standard conditions: 14.696 psia (101325 Pa), 15°C (288.15 K).

$$\dot{m}_{air,total} = \frac{Q_{SCFM} \times 0.000471947 \times P_{std}}{R_{air} \times T_{std}}$$

where $Q_{SCFM} \times 0.000471947$ converts SCFM to m³/s.

$$\dot{m}_{air,total} = Q_{SCFM} \times 0.000471947 \times \frac{101325}{287.05 \times 288.15}$$

$$\dot{m}_{air,total} \approx Q_{SCFM} \times 5.782 \times 10^{-4} \text{ kg/s}$$

The air is split:

$$\dot{m}_{air,tank} = f_{tank} \times \dot{m}_{air,total}$$

$$\dot{m}_{air,pump} = f_{pump} \times \dot{m}_{air,total}$$

where $f_{tank} + f_{pump} = 1$.

---

## 3. Liquid Mass Balance

$$\frac{dV_{liquid}}{dt} = -Q_{out,total}$$

where:

$$Q_{out,total} = Q_{pressure} + Q_{pump}$$

- $Q_{pressure}$ = flow driven by tank pressure differential (through hose)
- $Q_{pump}$ = flow from AODD pump (Scenarios B, C only)

Transferred volume (cumulative):

$$V_{transferred}(t) = V_{liquid,0} - V_{liquid}(t)$$

---

## 4. Pressure-Driven Flow Through Hose

### Available Pressure Differential

$$\Delta P_{available} = P_{tank}(t) - P_{receiver} - \rho_{liq} \cdot g \cdot \Delta z$$

where:
- $P_{tank}$ = current tank absolute pressure (Pa)
- $P_{receiver}$ = receiver absolute pressure (Pa)
- $\rho_{liq}$ = liquid density (kg/m³)
- $g = 9.81$ m/s²
- $\Delta z$ = elevation change (m), positive = receiver above tank

### Friction and Minor Losses

Total pressure drop at flow rate $Q$:

$$\Delta P_{loss}(Q) = \Delta P_{friction}(Q) + \Delta P_{minor}(Q)$$

**Darcy-Weisbach friction:**

$$\Delta P_{friction} = f \cdot \frac{L}{D} \cdot \frac{\rho_{liq} \cdot v^2}{2}$$

**Minor losses:**

$$\Delta P_{minor} = \Sigma K \cdot \frac{\rho_{liq} \cdot v^2}{2}$$

where velocity:

$$v = \frac{Q}{A} = \frac{4 \cdot Q}{\pi \cdot D^2}$$

### Combined — Solve for Q

At steady state for each time step:

$$\Delta P_{available} = \left(f \cdot \frac{L}{D} + \Sigma K\right) \cdot \frac{\rho_{liq} \cdot v^2}{2}$$

Solving for $v$:

$$v = \sqrt{\frac{2 \cdot \Delta P_{available}}{\rho_{liq} \cdot \left(f \cdot \frac{L}{D} + \Sigma K\right)}}$$

Then:

$$Q_{pressure} = v \cdot A = v \cdot \frac{\pi D^2}{4}$$

**Note:** $f$ depends on $v$ (through Reynolds number), making this implicit. In the Modelica model, we use an iterative/algebraic formulation — the ODE solver handles this naturally.

If $\Delta P_{available} \leq 0$, then $Q_{pressure} = 0$ (no reverse flow).

---

## 5. Friction Factor

### Reynolds Number

$$Re = \frac{\rho_{liq} \cdot v \cdot D}{\mu}$$

where $\mu$ is dynamic viscosity in Pa·s.

### Laminar (Re < 2300)

$$f = \frac{64}{Re}$$

### Turbulent (Re > 4000) — Swamee-Jain Approximation

The Swamee-Jain equation is an explicit approximation to the Colebrook-White equation:

$$f = \frac{0.25}{\left[\log_{10}\left(\frac{\varepsilon/D}{3.7} + \frac{5.74}{Re^{0.9}}\right)\right]^2}$$

where:
- $\varepsilon$ = pipe roughness (m)
- Valid for: $5000 \leq Re \leq 10^8$ and $10^{-6} \leq \varepsilon/D \leq 0.05$

### Transition Region (2300 ≤ Re ≤ 4000)

Linear interpolation between laminar $f$ at $Re=2300$ and turbulent $f$ at $Re=4000$:

$$f_{transition} = f_{lam,2300} + \frac{Re - 2300}{4000 - 2300} \cdot (f_{turb,4000} - f_{lam,2300})$$

This avoids a discontinuity in the friction factor that could cause solver issues.

---

## 6. AODD Pump Model (Simplified)

### Current Implementation (Placeholder)

$$Q_{pump} = \eta_{pump} \cdot \dot{m}_{air,pump} / \rho_{air,std}$$

Simplified further as:

$$Q_{pump} = \eta_{gpm/scfm} \cdot Q_{air,pump,SCFM}$$

where:
- $\eta_{gpm/scfm}$ = `pump_efficiency_gpm_per_scfm` (default 0.5 GPM per SCFM)
- $Q_{air,pump,SCFM} = f_{pump} \times Q_{SCFM,total}$

Converted to m³/s for the model:

$$Q_{pump} [m^3/s] = \eta_{gpm/scfm} \times Q_{air,pump,SCFM} \times 6.309 \times 10^{-5}$$

### Future Enhancement
Replace with manufacturer pump curve: $Q_{pump} = f(P_{discharge}, P_{suction}, \dot{m}_{air})$.

---

## 7. Pressure Limit Controller

The tanker must not exceed `max_tank_pressure_psig`.

### Logic

$$\dot{m}_{air,tank,actual} = \begin{cases} \dot{m}_{air,tank} & \text{if } P_{tank} < P_{max} \\ 0 & \text{if } P_{tank} \geq P_{max} \end{cases}$$

In Modelica, this is implemented with a smooth transition to avoid chattering:

```modelica
mdot_air_actual = mdot_air_tank * (if P_tank < P_max then 1.0 
                                   else max(0, 1 - (P_tank - P_max)/1000));
```

This creates a soft shutoff over a 1 kPa band above P_max.

---

## 8. Unit Conversions (Config → Model)

| Config Parameter | Config Unit | Model Unit | Conversion |
|-----------------|-------------|------------|------------|
| Volume (gal) | US gallons | m³ | × 0.00378541 |
| Pressure (psig) | psig | Pa (absolute) | (psig + 14.696) × 6894.76 |
| Pressure (psia) | psia | Pa | × 6894.76 |
| Viscosity (cP) | centipoise | Pa·s | × 0.001 |
| Hose diameter (in) | inches | m | × 0.0254 |
| Hose length (ft) | feet | m | × 0.3048 |
| Elevation (ft) | feet | m | × 0.3048 |
| Roughness (mm) | mm | m | × 0.001 |
| Temperature (°C) | Celsius | Kelvin | + 273.15 |
| SCFM | ft³/min (std) | m³/s | × 0.000471947 |
| GPM | gal/min | m³/s | × 6.30902e-5 |

---

## 9. Initial Conditions

| Variable | Initial Value |
|----------|--------------|
| $V_{liquid}(0)$ | `tanker_total_volume_gal × initial_fill_fraction` (converted to m³) |
| $V_{gas}(0)$ | `V_tank_total - V_liquid(0)` |
| $m_{gas}(0)$ | $\frac{P_{ambient} \cdot V_{gas}(0)}{R_{air} \cdot T}$ (tank starts at atmospheric) |
| $P_{tank}(0)$ | $P_{ambient}$ |
| $V_{transferred}(0)$ | 0 |

---

## 10. Assumptions and Limitations

| # | Assumption | Impact | Future Fix |
|---|-----------|--------|------------|
| 1 | Ideal gas | Accurate for P < 3 atm | Real gas EOS |
| 2 | Isothermal | Overpredicts pressure slightly | Add energy balance |
| 3 | Incompressible liquid | Excellent for oil | — |
| 4 | 1D lumped flow | No spatial effects in tank | CFD if needed |
| 5 | Quasi-steady friction | Good for slow transients | Unsteady friction |
| 6 | Simplified AODD pump | Constant efficiency | Manufacturer curve |
| 7 | No two-phase flow | Valid until tank nearly empty | Two-phase model |
| 8 | Smooth shutoff controller | Small error near P_max | Discrete controller |
