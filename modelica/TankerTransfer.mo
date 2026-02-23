// =============================================================================
// TankerTransfer.mo — Truck Tanker Liquid Transfer Simulation
// =============================================================================
//
// Physics-based model for pressurized liquid transfer from a truck tanker.
//
// Supports three operating modes via parameters:
//   Scenario A: Pressurize only (f_tank=1, f_pump=0)
//   Scenario B: Split air       (f_tank=0.5, f_pump=0.5)
//   Scenario C: Pump only       (f_tank=0, f_pump=1)
//
// See docs/MODEL_MATH.md for full equation derivations.
// =============================================================================

model TankerTransfer
  "Dynamic truck tanker liquid transfer via pressurization and/or AODD pump"

  // =========================================================================
  // PARAMETERS — Set from scenario config via -override
  // =========================================================================

  // --- Tank geometry (SI units: m³) ---
  parameter Real V_tank_total(unit="m3") = 17.034
    "Total tank volume [m³] (default: 4500 gal)";
  parameter Real V_liquid_0(unit="m3") = 15.331
    "Initial liquid volume [m³] (default: 4050 gal = 90% of 4500)";

  // --- Pressure limits (SI units: Pa absolute) ---
  parameter Real P_max(unit="Pa") = 308168.0
    "Maximum tank pressure [Pa abs] (default: 30 psig + 14.7 psia)";
  parameter Real P_ambient(unit="Pa") = 101325.0
    "Ambient/atmospheric pressure [Pa abs] (default: 14.7 psia)";
  parameter Real P_receiver(unit="Pa") = 101325.0
    "Receiver pressure [Pa abs] (default: 0 psig = 14.7 psia)";

  // --- Temperature ---
  parameter Real T(unit="K") = 298.15
    "Gas temperature [K] (default: 25°C)";

  // --- Air supply (SI units: kg/s) ---
  parameter Real mdot_air_total(unit="kg/s") = 0.01098
    "Total air mass flow rate [kg/s] (default: 19 SCFM)";
  parameter Real f_tank(unit="1") = 1.0
    "Fraction of air to tank pressurization [0..1]";
  parameter Real f_pump(unit="1") = 0.0
    "Fraction of air to AODD pump [0..1]";

  // --- Liquid properties ---
  parameter Real rho_liq(unit="kg/m3") = 880.0
    "Liquid density [kg/m³]";
  parameter Real mu_liq(unit="Pa.s") = 0.22
    "Liquid dynamic viscosity [Pa·s] (default: 220 cP)";

  // --- Hose/pipe geometry ---
  parameter Real D_hose(unit="m") = 0.0508
    "Hose internal diameter [m] (default: 2.0 in)";
  parameter Real L_hose(unit="m") = 15.24
    "Hose length [m] (default: 50 ft)";
  parameter Real eps_rough(unit="m") = 0.0
    "Pipe roughness [m] (default: smooth)";
  parameter Real K_minor(unit="1") = 5.0
    "Total minor loss coefficient";
  parameter Real dz(unit="m") = 0.0
    "Elevation change [m] (positive = receiver above tank)";

  // --- AODD pump ---
  parameter Real Q_pump_per_scfm_air(unit="m3/s") = 3.155e-5
    "Pump volumetric output per SCFM of air [m³/s per SCFM] (default: 0.5 GPM/SCFM)";
  // Note: This converts as follows:
  //   0.5 GPM/SCFM * 6.309e-5 m³/s/GPM = 3.155e-5 m³/s per SCFM
  //   The runner converts from config units.

  // --- Constants ---
  constant Real R_air = 287.05 "Specific gas constant for air [J/(kg·K)]";
  constant Real g = 9.81 "Gravitational acceleration [m/s²]";
  constant Real pi = 3.14159265358979 "Pi constant";

  // =========================================================================
  // VARIABLES
  // =========================================================================

  // --- State variables ---
  Real m_gas(start = 0, fixed = false, unit="kg")
    "Mass of gas in ullage [kg]";
  Real V_liquid(start = 0, fixed = false, unit="m3")
    "Volume of liquid remaining in tank [m³]";

  // --- Derived quantities ---
  Real V_gas(unit="m3") "Ullage gas volume [m³]";
  Real P_tank(unit="Pa") "Tank absolute pressure [Pa]";
  Real P_tank_psig "Tank gauge pressure [psig] (for output)";

  Real dP_avail(unit="Pa") "Available pressure differential [Pa]";
  Real v_hose(unit="m/s") "Liquid velocity in hose [m/s]";
  Real A_hose(unit="m2") "Hose cross-sectional area [m²]";
  Real Re "Reynolds number";
  Real f_darcy "Darcy friction factor";
  Real loss_coeff "Total loss coefficient (fL/D + K)";

  Real Q_pressure(unit="m3/s") "Flow rate from pressurization [m³/s]";
  Real Q_pump_flow(unit="m3/s") "Flow rate from AODD pump [m³/s]";
  Real Q_total(unit="m3/s") "Total outlet flow [m³/s]";
  Real Q_total_gpm "Total outlet flow [GPM] (for output)";

  Real V_transferred(unit="m3") "Cumulative transferred volume [m³]";
  Real V_transferred_gal "Cumulative transferred volume [gal]";
  Real V_liquid_gal "Remaining liquid volume [gal]";

  Real mdot_air_tank_cmd(unit="kg/s") "Commanded air flow to tank [kg/s]";
  Real mdot_air_tank(unit="kg/s") "Actual air flow to tank (after controller) [kg/s]";
  Real Q_air_pump_scfm "Air flow to pump [SCFM] (for pump model)";

  // --- Conversion constants ---
  parameter Real gal_per_m3 = 264.172 "Gallons per cubic meter";
  parameter Real Pa_per_psi = 6894.76 "Pascals per psi";
  // SCFM conversion factor: 1 SCFM = 4.7195e-4 m³/s at standard conditions
  // mdot = Q_std * P_std / (R_air * T_std) => 1 SCFM => 5.782e-4 kg/s
  parameter Real kg_s_per_scfm = 5.782e-4 "kg/s per SCFM";

  // --- Pre-computed pipe constants (avoid recalculating every step) ---
  // Laminar Hagen-Poiseuille resistance: dP_lam = a_lam * Q
  //   a_lam = 128 * mu * L / (pi * D^4)
  parameter Real a_lam = 128.0 * mu_liq * L_hose / (pi * D_hose^4)
    "Laminar resistance coefficient [Pa·s/m³]";
  // Minor loss quadratic coefficient: dP_minor = b_minor * Q * |Q|
  //   b_minor = K * rho / (2 * A^2)
  parameter Real A_hose_param = pi * D_hose^2 / 4.0
    "Hose cross-sectional area [m²]";
  parameter Real b_minor = K_minor * rho_liq / (2.0 * A_hose_param^2)
    "Minor loss coefficient [Pa·s²/m⁶]";

initial equation
  // Initial liquid volume
  V_liquid = V_liquid_0;
  // Initial gas mass: tank starts at atmospheric pressure
  m_gas = P_ambient * (V_tank_total - V_liquid_0) / (R_air * T);

equation
  // =========================================================================
  // GAS DYNAMICS
  // =========================================================================

  // Ullage volume = total - liquid
  V_gas = V_tank_total - V_liquid;

  // Ideal gas law for tank pressure
  P_tank = m_gas * R_air * T / (max(V_gas, 1e-6));
  // max() prevents division by zero if tank is completely full

  // Gauge pressure for output
  P_tank_psig = (P_tank - P_ambient) / Pa_per_psi;

  // --- Pressure Controller ---
  // Commanded air to tank (before pressure limit)
  mdot_air_tank_cmd = f_tank * mdot_air_total;

  // Soft shutoff: linearly ramp down over 2000 Pa above P_max
  // This avoids discontinuity that can cause solver chattering
  mdot_air_tank = if P_tank < P_max then
                    mdot_air_tank_cmd
                  else
                    mdot_air_tank_cmd * max(0.0, 1.0 - (P_tank - P_max) / 2000.0);

  // Gas mass balance
  der(m_gas) = mdot_air_tank;

  // =========================================================================
  // HOSE FLOW — Explicit quadratic formula (NO algebraic loop)
  // =========================================================================
  //
  // The pressure drop through the hose is:
  //   dP = a_lam * Q  +  b_minor * Q²
  // where:
  //   a_lam   = 128·μ·L / (π·D⁴)   (Hagen-Poiseuille laminar resistance)
  //   b_minor = K·ρ / (2·A²)         (minor loss quadratic term)
  //
  // Solving for Q (positive root of quadratic):
  //   b_minor·Q² + a_lam·Q - dP = 0
  //   Q = (-a_lam + sqrt(a_lam² + 4·b_minor·dP)) / (2·b_minor)
  //
  // If b_minor ≈ 0 (no minor losses): Q = dP / a_lam
  //
  // This is EXPLICIT in Q — no implicit velocity-Re-friction loop.
  // Valid for laminar flow (Re < 2300), which applies here because
  // μ = 0.22 Pa·s ⟹ Re ≈ 203·v, so Re < 2300 for v < 11.3 m/s.
  // =========================================================================

  // Available driving pressure
  dP_avail = P_tank - P_receiver - rho_liq * g * dz;

  // Hose cross-section area (output variable = parameter value)
  A_hose = A_hose_param;

  // Explicit flow rate from quadratic formula
  Q_pressure = if dP_avail > 0 and V_liquid > 1e-6 then
                 (if b_minor > 1e-10 then
                    (-a_lam + sqrt(a_lam * a_lam + 4.0 * b_minor * dP_avail)) / (2.0 * b_minor)
                  else
                    dP_avail / max(a_lam, 1e-10))
               else
                 0.0;

  // Hose velocity (for output / diagnostics)
  v_hose = Q_pressure / max(A_hose, 1e-10);

  // Reynolds number (for output only — not used in flow calculation)
  Re = rho_liq * abs(v_hose) * D_hose / mu_liq;

  // Darcy friction factor (for output only — informational)
  f_darcy = if Re > 1e-6 then 64.0 / Re else 0.0;

  // Total loss coefficient (for output only)
  loss_coeff = f_darcy * L_hose / D_hose + K_minor;

  // =========================================================================
  // AODD PUMP FLOW
  // =========================================================================

  // Air to pump in SCFM
  Q_air_pump_scfm = f_pump * mdot_air_total / kg_s_per_scfm;

  // Pump flow (simplified: proportional to air supply)
  // Only produces flow if liquid is available
  Q_pump_flow = if V_liquid > 1e-6 then
                  Q_pump_per_scfm_air * Q_air_pump_scfm
                else
                  0.0;

  // =========================================================================
  // TOTAL FLOW AND LIQUID BALANCE
  // =========================================================================

  Q_total = Q_pressure + Q_pump_flow;
  Q_total_gpm = Q_total * gal_per_m3 * 60.0;
  // m³/s * 264.172 gal/m³ * 60 s/min = GPM

  // Liquid volume balance (decreases as liquid exits)
  der(V_liquid) = -Q_total;

  // =========================================================================
  // OUTPUT TRACKING
  // =========================================================================

  V_transferred = V_liquid_0 - V_liquid;
  V_transferred_gal = V_transferred * gal_per_m3;
  V_liquid_gal = V_liquid * gal_per_m3;

  annotation(
    experiment(StartTime = 0, StopTime = 7200, NumberOfIntervals = 7200, Tolerance = 1e-6),
    Documentation(info = "<html>
      <p>Truck tanker liquid transfer model.</p>
      <p>Simulates pressurization, AODD pump, and combined strategies.</p>
      <p>See docs/MODEL_MATH.md for equations.</p>
    </html>")
  );

end TankerTransfer;
