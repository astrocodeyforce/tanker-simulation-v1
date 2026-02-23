# MODEL MATH

## Overview

This document describes the physics equations implemented in `TankerTransferV2.mo`.
The model is **1D lumped-parameter** — no spatial gradients, single pressure/temperature per compartment.

**V2 improvements over V1:**
- Horizontal cylindrical tank geometry with algebraic liquid-level solve
- Multi-segment pipe network (valve + 2 pipe segments in series)
- Smooth friction factor blend (cubic smoothstep, laminar ↔ turbulent)
- Valve K-model with opening fraction
- Pressure relief valve (subsonic orifice)
- Compressor soft ramp-down near pressure cap
- All parameters configurable via YAML → override

---

## 1. System Schematic

```
         Compressed Air In
              │ ṁ_air_in
              ▼
    ┌─────────────────────────────┐
    │      ULLAGE GAS (ideal)     │  P_tank, V_gas, T_gas_0
    │      m_gas, isothermal      │
    ├ ─ ─ ─ ─ ─ ─ liquid level ─ ┤  h_liquid (horizontal cylinder)
    │      LIQUID (incompress.)   │  V_liquid, ρ_L, μ_L
    │      DOT-407 horiz. cyl.    │
    └──────────────┬──────────────┘
                   │                       ┌──── Relief Valve ───► Atmosphere
                   │                       │     (P > P_relief)
                   ▼                       │
    ┌──────────────┴──────────────┐
    │  OUTLET VALVE (K model)     │  K_valve_eff = K_open / u²
    │  bore D_valve, opening u    │
    └──────────────┬──────────────┘
                   │  Q_L (series flow through all segments)
                   ▼
    ┌─────────────────────────────┐
    │  PIPE SEGMENT 1             │  D_pipe1, L_pipe1, ε_pipe1, K_pipe1
    │  (Darcy-Weisbach + minors)  │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │  PIPE SEGMENT 2             │  D_pipe2, L_pipe2, ε_pipe2, K_pipe2
    │  (Darcy-Weisbach + minors)  │
    └──────────────┬──────────────┘
                   │
                   ▼  + elevation Δz
    ┌─────────────────────────────┐
    │  RECEIVER                   │  P_receiver (constant)
    └─────────────────────────────┘
```

---

## 2. State Variables

| Variable | Symbol | Unit | Description |
|----------|--------|------|-------------|
| Gas mass | $m_{gas}$ | kg | Air mass in ullage headspace |
| Liquid volume | $V_{liquid}$ | m³ | Liquid remaining in tank |

Both are ODE-governed. All other quantities are algebraic.

---

## 3. Gas Compressibility (Ideal Gas, Isothermal)

### Assumption

- Gas behaves as ideal gas (air at moderate pressures ≤ 25 psig ≈ 2.7 atm absolute)
- Isothermal process (temperature constant at $T_{gas,0}$)

### Equations

Gas volume equals the tank void space:

$$V_{gas}(t) = V_{tank} - V_{liquid}(t)$$

Tank pressure from ideal gas law:

$$P_{tank}(t) = \frac{m_{gas}(t) \cdot R_{air} \cdot T_{gas,0}}{\max(V_{gas}(t),\, 10^{-6})}$$

where:
- $R_{air} = 287.05$ J/(kg·K) — specific gas constant for air
- $T_{gas,0}$ = gas temperature (K), constant
- $P_{tank}$ is **absolute** pressure (Pa)

Gauge pressure:

$$P_{gauge} = P_{tank} - P_{atm}$$

### Air Mass Balance

$$\frac{dm_{gas}}{dt} = \dot{m}_{air,in} - \dot{m}_{relief}$$

where $\dot{m}_{air,in}$ is the compressor feed and $\dot{m}_{relief}$ is the relief valve outflow.

---

## 4. Horizontal Cylinder Geometry

### Tank Dimensions

For a DOT-407 horizontal cylindrical tanker:

$$L_{tank,eff} = \begin{cases} L_{tank} & \text{if } L_{tank} > 0 \\ \displaystyle\frac{V_{tank}}{\pi R_{tank}^2} & \text{otherwise (auto-calc)} \end{cases}$$

where $R_{tank} = D_{tank}/2$.

### Liquid Cross-Section Area

For liquid height $h$ in a horizontal cylinder of radius $R$:

$$A_{cross}(h) = R^2 \cos^{-1}\!\left(\frac{R-h}{R}\right) - (R-h)\sqrt{2Rh - h^2}$$

Clamped:
- $A_{cross} = 0$ when $h \leq 0$
- $A_{cross} = \pi R^2$ when $h \geq D_{tank}$

### Volume–Height Relation (Algebraic Constraint)

$$V_{liquid} = L_{tank,eff} \cdot A_{cross}(h_{liquid})$$

The Modelica solver inverts this relation algebraically to find $h_{liquid}(t)$ at each time step — no explicit root-finding needed.

### Hydrostatic Head

Outlet is at the bottom of the cylinder:

$$\Delta P_{head} = \rho_L \cdot g \cdot h_{liquid}$$

---

## 5. Liquid Mass Balance

$$\frac{dV_{liquid}}{dt} = -Q_L$$

where $Q_L$ is the volumetric flow rate through the discharge pipeline (m³/s).

Tracked outputs:

$$V_{transferred}(t) = V_{liquid,0} - V_{liquid}(t)$$

---

## 6. Driving Pressure

The net pressure available to push liquid through the discharge system:

$$\Delta P_{drive} = P_{gauge} + \Delta P_{head} - (P_{receiver} - P_{atm}) - \rho_L \cdot g \cdot \Delta z_{total}$$

where:
- $P_{gauge}$ = tank gauge pressure (Pa)
- $\Delta P_{head}$ = hydrostatic head from liquid column height (Pa)
- $P_{receiver}$ = receiver absolute pressure (Pa)
- $\Delta z_{total}$ = elevation gain from tank outlet to receiver (m)

---

## 7. Outlet Valve Model

The valve is modeled as a pure minor-loss element with K dependent on opening fraction $u$:

$$K_{valve,eff} = \frac{K_{valve,open}}{\max(u^2,\, 0.01)}$$

where:
- $K_{valve,open}$ = loss coefficient when fully open (default 0.2)
- $u$ = opening fraction [0, 1] (default 1.0)

Pressure drop across valve:

$$\Delta P_{valve} = K_{valve,eff} \cdot \frac{\rho_L \, v_{valve} |v_{valve}|}{2}$$

Velocity through valve:

$$v_{valve} = \frac{Q_L}{A_{valve}}, \quad A_{valve} = \frac{\pi D_{valve}^2}{4}$$

---

## 8. Multi-Segment Pipe Network

The discharge consists of **two pipe segments in series** — same volumetric flow $Q_L$ passes through both.

### Per-Segment Pressure Drop

For segment $i$ ($i = 1, 2$):

**Velocity:**

$$v_i = \frac{Q_L}{A_i}, \quad A_i = \frac{\pi D_i^2}{4}$$

**Reynolds number:**

$$Re_i = \frac{\rho_L \cdot |v_i| \cdot D_i}{\mu_L}$$

**Major loss (Darcy-Weisbach friction):**

$$\Delta P_{friction,i} = f_i \cdot \frac{L_i}{D_i} \cdot \frac{\rho_L \, v_i |v_i|}{2}$$

**Minor losses (fittings, elbows, etc.):**

$$\Delta P_{minor,i} = K_i \cdot \frac{\rho_L \, v_i |v_i|}{2}$$

**Total segment drop:**

$$\Delta P_{seg,i} = \Delta P_{friction,i} + \Delta P_{minor,i}$$

### Total Pipeline Loss

$$\Delta P_{loss,total} = \Delta P_{valve} + \Delta P_{seg,1} + \Delta P_{seg,2}$$

---

## 9. Friction Factor

### Smooth Laminar-Turbulent Blend

The function `smoothFriction(Re, ε, D)` returns the Darcy friction factor with a **cubic smoothstep** blend in the transition zone to avoid solver discontinuities.

#### Laminar ($Re < 2000$)

$$f_{lam} = \frac{64}{Re}$$

#### Turbulent ($Re > 4000$) — Swamee-Jain Approximation

$$f_{turb} = \frac{0.25}{\left[\log_{10}\!\left(\dfrac{\varepsilon/D}{3.7} + \dfrac{5.74}{Re^{0.9}}\right)\right]^2}$$

Valid for $5000 \leq Re \leq 10^8$ and $10^{-6} \leq \varepsilon/D \leq 0.05$.

#### Transition Zone ($2000 \leq Re \leq 4000$) — Cubic Smoothstep

$$s = \frac{Re - 2000}{2000}$$

$$s \leftarrow s^2(3 - 2s) \quad \text{(Hermite smoothstep)}$$

$$f = (1-s) \cdot f_{lam} + s \cdot f_{turb}$$

This ensures $C^1$ continuity at both $Re = 2000$ and $Re = 4000$.

---

## 10. Flow Equation (Algebraic)

The system solves for $Q_L$ such that driving pressure equals total loss:

$$\boxed{\Delta P_{drive} = \Delta P_{loss,total}} \quad \text{when } Q_L > 0$$

If $\Delta P_{drive} \leq 0$ or $V_{liquid} \leq V_{liquid,min}$:

$$Q_L = 0$$

This is an **implicit algebraic equation** — the ODE solver (DASSL) handles it naturally as part of the DAE system. No explicit root-finding or iteration is needed.

---

## 11. Air Inlet Model (Compressor Controller)

### Constant SCFM Mode with Soft Shutoff

$$\dot{m}_{air,in} = \begin{cases}
\dot{m}_{air,max} & \text{if } P_{tank} < P_{max,abs} \\[6pt]
\dot{m}_{air,max} \cdot \max\!\left(0,\; 1 - \dfrac{P_{tank} - P_{max,abs}}{5000}\right) & \text{if } P_{tank} \geq P_{max,abs}
\end{cases}$$

where:
- $\dot{m}_{air,max}$ = nominal compressor mass flow rate (kg/s), converted from SCFM
- $P_{max,abs} = P_{atm} + P_{max,gauge}$ = absolute pressure cap
- The 5 kPa (≈ 0.7 psi) ramp-down band prevents solver chattering

### SCFM → kg/s Conversion

Standard conditions: 14.696 psia (101325 Pa), 15°C (288.15 K).

$$\dot{m}_{air} = Q_{SCFM} \times 0.000471947 \times \frac{P_{std}}{R_{air} \times T_{std}}$$

$$\dot{m}_{air} \approx Q_{SCFM} \times 5.782 \times 10^{-4} \text{ kg/s}$$

---

## 12. Pressure Relief Valve

Opens when tank pressure exceeds the relief setpoint.

### Model (Subsonic Orifice Flow)

$$\dot{m}_{relief} = \begin{cases}
C_d \cdot A_{relief} \cdot \sqrt{2 \cdot (P_{tank} - P_{atm}) \cdot \dfrac{P_{tank}}{R_{air} \cdot T_{gas,0}}} & \text{if } P_{tank} > P_{relief,abs} \\[6pt]
0 & \text{otherwise}
\end{cases}$$

where:
- $C_d$ = discharge coefficient (default 0.62)
- $A_{relief} = \pi (D_{relief}/2)^2$ = relief orifice area
- $P_{relief,abs} = P_{atm} + P_{relief,gauge}$ (default 27.5 psig)

---

## 13. Unit Conversions (YAML Config → Model)

| Config Parameter | Config Unit | Model Unit | Conversion |
|:----------------|:-----------|:----------|:-----------|
| Volume | US gallons | m³ | × 0.00378541 |
| Pressure | psig | Pa (absolute) | (psig + 14.696) × 6894.76 |
| Viscosity | cP (centipoise) | Pa·s | × 0.001 |
| Diameter | inches | m | × 0.0254 |
| Pipe length | feet | m | × 0.3048 |
| Elevation | feet | m | × 0.3048 |
| Roughness | mm | m | × 0.001 |
| Temperature | °C | K | + 273.15 |
| SCFM | ft³/min (std) | kg/s | × 5.782 × 10⁻⁴ |

All conversions performed in `scripts/yaml_to_override_v2.py` before passing to OpenModelica.

---

## 14. Initial Conditions

| Variable | Formula |
|:---------|:--------|
| $V_{liquid}(0)$ | `V_liquid_0` (from config, converted to m³) |
| $m_{gas}(0)$ | $\dfrac{P_{tank,0} \cdot (V_{tank} - V_{liquid,0})}{R_{air} \cdot T_{gas,0}}$ |

The tank starts at the specified initial pressure (typically atmospheric) with gas filling the headspace above the liquid.

---

## 15. Numerical Strategy

| Property | Value |
|:---------|:------|
| DAE solver | DASSL (default in OpenModelica) |
| Tolerance | $10^{-6}$ |
| Equations | 30 algebraic + 2 ODEs |
| Variables | 30 |

The model is a DAE index-1 system. The solver handles:
- Implicit $Q_L$ solve (drive = loss balance)
- Implicit $h_{liquid}$ solve (cylinder cross-section inversion)
- Smooth switching (compressor shutoff, relief valve opening)

---

## 16. Assumptions and Limitations

| # | Assumption | Impact | Potential Enhancement |
|:--|:----------|:-------|:---------------------|
| 1 | Ideal gas | Accurate for P < 3 atm | Real gas EOS |
| 2 | Isothermal | Overpredicts pressure slightly | Add energy balance |
| 3 | Incompressible liquid | Excellent for liquids | — |
| 4 | 1D lumped flow | No spatial gradients | CFD if needed |
| 5 | Quasi-steady friction | Good for slow transients | Unsteady friction |
| 6 | Newtonian viscosity | Constant μ | Power-law non-Newtonian (k, n) |
| 7 | No two-phase flow | Valid until tank nearly empty | Two-phase model |
| 8 | Constant receiver pressure | No storage dynamics | Dynamic receiver model |
| 9 | Horizontal cylinder (no baffles) | Clean level-volume mapping | Baffled tank correction |
| 10 | Two pipe segments | Adequate for most field setups | N-segment generalization |

---

## 17. V2 Default Parameter Values

| Parameter | Default | Unit | Description |
|:----------|:--------|:-----|:------------|
| V_tank | 26.498 | m³ | 7000 US gal |
| D_tank | 1.905 | m | 75 in (DOT-407) |
| V_liquid_0 | 24.605 | m³ | 6500 gal initial fill |
| P_atm | 101325 | Pa | Standard atmosphere |
| P_max_gauge | 172369 | Pa | 25 psig |
| P_relief_gauge | 189606 | Pa | 27.5 psig |
| mdot_air_max | 0.01098 | kg/s | 19 SCFM |
| rho_L | 1050 | kg/m³ | Latex emulsion |
| mu_L | 0.1 | Pa·s | 100 cP |
| D_pipe | 0.0762 | m | 3 in discharge |
| L_pipe (each) | 7.62 | m | 25 ft per segment |
| ε_pipe | 1e-5 | m | Smooth stainless |
| K_valve_open | 0.2 | — | Full-bore ball valve |
| D_relief | 0.0254 | m | 1 in relief orifice |
| Cd_relief | 0.62 | — | Sharp-edge orifice |
| T_gas_0 | 293.15 | K | 20 °C |
