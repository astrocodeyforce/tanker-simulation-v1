// =============================================================================
// TankerTransferV2.mo — Realistic Tanker Air-Displacement Unloading Model
// =============================================================================
// Version 2: Full rebuild with horizontal cylinder geometry, multi-segment
// pipe network, compressor model, relief valve, and dynamic parameters.
//
// Build approach: incremental — this skeleton compiles first, then we add.
// =============================================================================

model TankerTransferV2
  "Realistic air-displacement unloading of a horizontal cylindrical tanker"

  // =========================================================================
  // CONSTANTS
  // =========================================================================
  constant Real R_air = 287.05 "Specific gas constant for air [J/(kg·K)]";
  constant Real g_acc = 9.80665 "Gravitational acceleration [m/s²]";
  constant Real pi = 3.14159265358979 "Pi";
  constant Real gamma_air = 1.4 "Heat capacity ratio for air";

  // =========================================================================
  // PARAMETERS — All set via -override from YAML config
  // =========================================================================

  // --- Tank geometry (horizontal cylinder) ---
  parameter Real V_tank(unit="m3") = 26.498
    "Total tank internal volume [m³] (default 7000 gal)";
  parameter Real D_tank(unit="m") = 1.905
    "Tank internal diameter [m] (default ~75 in for DOT-407)";
  parameter Real L_tank(unit="m") = 0
    "Tank length [m] (0 = auto-calc from V_tank and D_tank)";

  // --- Initial conditions ---
  parameter Real V_liquid_0(unit="m3") = 24.605
    "Initial liquid volume [m³] (default 6500 gal)";
  parameter Real P_atm(unit="Pa") = 101325.0
    "Atmospheric pressure [Pa]";
  parameter Real P_tank_0(unit="Pa") = 101325.0
    "Initial tank absolute pressure [Pa]";
  parameter Real T_gas_0(unit="K") = 293.15
    "Initial gas temperature [K] (default 20°C)";

  // --- Pressure limits ---
  parameter Real P_max_gauge(unit="Pa") = 172369.0
    "Max allowed gauge pressure [Pa] (default 25 psig)";

  // --- Air supply (constant SCFM mode) ---
  parameter Real mdot_air_max(unit="kg/s") = 0.01098
    "Max air mass inflow [kg/s] (default 19 SCFM)";

  // --- Compressor curve ---
  parameter Real c_clearance(unit="1") = 0.04
    "Compressor clearance ratio: 0=constant/plant air, 0.02=rotary vane, 0.04=reciprocating";

  // --- Liquid properties ---
  parameter Real rho_L(unit="kg/m3") = 1000.0
    "Liquid density [kg/m³]";
  parameter Real mu_L(unit="Pa.s") = 0.1
    "Liquid dynamic viscosity [Pa·s] (default 100 cP) — consistency index K for power-law fluids";
  parameter Real n_power_law(unit="1") = 1.0
    "Power-law flow index: 1.0=Newtonian, <1=shear-thinning, >1=shear-thickening";

  // --- Outlet valve ---
  parameter Real D_valve(unit="m") = 0.0762
    "Outlet valve bore diameter [m] (default 3 in)";
  parameter Real K_valve_open(unit="1") = 0.2
    "Valve minor-loss K when fully open";
  parameter Real u_valve(unit="1") = 1.0
    "Valve opening fraction [0..1]";

  // --- Discharge pipe segment 1 ---
  parameter Real D_pipe1(unit="m") = 0.0762
    "Segment 1 inner diameter [m] (default 3 in)";
  parameter Real L_pipe1(unit="m") = 8.0
    "Segment 1 length [m]";
  parameter Real eps_pipe1(unit="m") = 1e-5
    "Segment 1 roughness [m]";
  parameter Real K_pipe1(unit="1") = 1.0
    "Segment 1 minor loss K (fittings)";

  // --- Discharge pipe segment 2 ---
  parameter Real D_pipe2(unit="m") = 0.0762
    "Segment 2 inner diameter [m] (default 3 in)";
  parameter Real L_pipe2(unit="m") = 8.0
    "Segment 2 length [m]";
  parameter Real eps_pipe2(unit="m") = 1e-5
    "Segment 2 roughness [m]";
  parameter Real K_pipe2(unit="1") = 1.0
    "Segment 2 minor loss K (fittings)";

  // --- Discharge pipe segment 3 (inactive by default: L=0) ---
  parameter Real D_pipe3(unit="m") = 0.0762
    "Segment 3 inner diameter [m]";
  parameter Real L_pipe3(unit="m") = 0.0
    "Segment 3 length [m] (0 = not used)";
  parameter Real eps_pipe3(unit="m") = 1e-5
    "Segment 3 roughness [m]";
  parameter Real K_pipe3(unit="1") = 0.0
    "Segment 3 minor loss K";

  // --- Discharge pipe segment 4 (inactive by default: L=0) ---
  parameter Real D_pipe4(unit="m") = 0.0762
    "Segment 4 inner diameter [m]";
  parameter Real L_pipe4(unit="m") = 0.0
    "Segment 4 length [m] (0 = not used)";
  parameter Real eps_pipe4(unit="m") = 1e-5
    "Segment 4 roughness [m]";
  parameter Real K_pipe4(unit="1") = 0.0
    "Segment 4 minor loss K";

  // --- Discharge pipe segment 5 (inactive by default: L=0) ---
  parameter Real D_pipe5(unit="m") = 0.0762
    "Segment 5 inner diameter [m]";
  parameter Real L_pipe5(unit="m") = 0.0
    "Segment 5 length [m] (0 = not used)";
  parameter Real eps_pipe5(unit="m") = 1e-5
    "Segment 5 roughness [m]";
  parameter Real K_pipe5(unit="1") = 0.0
    "Segment 5 minor loss K";

  // --- Elevation and receiver ---
  parameter Real dz_total(unit="m") = 0.0
    "Elevation change outlet to receiver [m] (+ve = lifting)";
  parameter Real P_receiver(unit="Pa") = 101325.0
    "Receiver absolute pressure [Pa]";

  // --- Relief valve ---
  parameter Real P_relief_gauge(unit="Pa") = 189606.0
    "Relief valve opening gauge pressure [Pa] (default 27.5 psig)";
  parameter Real Cd_relief(unit="1") = 0.62
    "Relief valve discharge coefficient";
  parameter Real D_relief(unit="m") = 0.0254
    "Relief valve orifice diameter [m] (default 1 in)";

  // --- Valve timing ---
  parameter Real t_valve_open(unit="s") = 0
    "Time when outlet valve opens [s] (0 = open from start, >0 = pre-pressurize first)";

  // --- Simulation ---
  parameter Real V_liquid_min(unit="m3") = 0.038
    "Minimum liquid volume before stop [m³] (default ~10 gal)";

  // --- Two-phase end-of-unload ---
  parameter Real D_outlet(unit="m") = 0.0762
    "Outlet nozzle diameter [m] (default 3 in) — two-phase onset when h_liquid < D_outlet";

  // =========================================================================
  // DERIVED PARAMETERS (computed once at init)
  // =========================================================================
  parameter Real P_max_abs = P_atm + P_max_gauge
    "Max absolute pressure [Pa]";
  parameter Real P_relief_abs = P_atm + P_relief_gauge
    "Relief opening absolute pressure [Pa]";
  parameter Real R_tank = D_tank / 2.0
    "Tank radius [m]";
  parameter Real L_tank_eff = if L_tank > 0 then L_tank
    else V_tank / (pi * R_tank * R_tank)
    "Effective tank length [m]";
  parameter Real A_relief = pi * (D_relief/2)^2
    "Relief orifice area [m²]";

  // Pipe areas
  parameter Real A_valve = pi * (D_valve/2)^2 "Valve flow area [m²]";
  parameter Real A_pipe1 = pi * (D_pipe1/2)^2 "Pipe seg 1 flow area [m²]";
  parameter Real A_pipe2 = pi * (D_pipe2/2)^2 "Pipe seg 2 flow area [m²]";
  parameter Real A_pipe3 = pi * (D_pipe3/2)^2 "Pipe seg 3 flow area [m²]";
  parameter Real A_pipe4 = pi * (D_pipe4/2)^2 "Pipe seg 4 flow area [m²]";
  parameter Real A_pipe5 = pi * (D_pipe5/2)^2 "Pipe seg 5 flow area [m²]";

  // =========================================================================
  // STATE VARIABLES
  // =========================================================================
  Real m_gas(start=0, fixed=false, unit="kg")
    "Gas mass in headspace [kg]";
  Real V_liquid(start=0, fixed=false, unit="m3")
    "Liquid volume in tank [m³]";

  // =========================================================================
  // ALGEBRAIC VARIABLES
  // =========================================================================

  // Gas / tank
  Real V_gas(unit="m3") "Gas headspace volume [m³]";
  Real P_tank(unit="Pa") "Tank absolute pressure [Pa]";
  Real P_gauge(unit="Pa") "Tank gauge pressure [Pa]";
  Real P_tank_psig "Tank gauge pressure [psig]";

  // Liquid level in horizontal cylinder
  Real h_liquid(unit="m", start=D_tank*0.5) "Liquid height from bottom of cylinder [m]";
  Real A_cross_liquid(unit="m2") "Liquid cross-section area [m²]";

  // Driving pressure
  Real dP_drive(unit="Pa") "Net driving pressure for liquid flow [Pa]";
  Real dP_head(unit="Pa") "Hydrostatic head at outlet [Pa]";

  // Flow (total through all segments in series)
  Real Q_L(unit="m3/s") "Volumetric liquid flow rate [m³/s]";
  Real Q_L_gpm "Flow rate [GPM]";

  // Per-segment velocities, Re, friction
  Real v_valve(unit="m/s") "Velocity through valve [m/s]";
  Real v_pipe1(unit="m/s") "Velocity in pipe segment 1 [m/s]";
  Real v_pipe2(unit="m/s") "Velocity in pipe segment 2 [m/s]";
  Real v_pipe3(unit="m/s") "Velocity in pipe segment 3 [m/s]";
  Real v_pipe4(unit="m/s") "Velocity in pipe segment 4 [m/s]";
  Real v_pipe5(unit="m/s") "Velocity in pipe segment 5 [m/s]";
  Real Re_valve "Reynolds number at valve";
  Real Re_pipe1 "Reynolds number in pipe 1";
  Real Re_pipe2 "Reynolds number in pipe 2";
  Real Re_pipe3 "Reynolds number in pipe 3";
  Real Re_pipe4 "Reynolds number in pipe 4";
  Real Re_pipe5 "Reynolds number in pipe 5";
  Real f_pipe1 "Darcy friction factor pipe 1";
  Real f_pipe2 "Darcy friction factor pipe 2";
  Real f_pipe3 "Darcy friction factor pipe 3";
  Real f_pipe4 "Darcy friction factor pipe 4";
  Real f_pipe5 "Darcy friction factor pipe 5";

  // Pressure drops per segment
  Real dP_valve(unit="Pa") "Pressure drop across valve [Pa]";
  Real dP_seg1(unit="Pa") "Pressure drop in pipe segment 1 [Pa]";
  Real dP_seg2(unit="Pa") "Pressure drop in pipe segment 2 [Pa]";
  Real dP_seg3(unit="Pa") "Pressure drop in pipe segment 3 [Pa]";
  Real dP_seg4(unit="Pa") "Pressure drop in pipe segment 4 [Pa]";
  Real dP_seg5(unit="Pa") "Pressure drop in pipe segment 5 [Pa]";
  Real dP_loss_total(unit="Pa") "Total liquid-side pressure loss [Pa]";

  // Air flows
  Real mdot_air_in(unit="kg/s") "Actual air mass inflow [kg/s]";
  Real mdot_relief(unit="kg/s") "Relief valve mass outflow [kg/s]";

  // Compressor curve
  Real r_comp "Compression pressure ratio P_tank/P_atm";
  Real eta_vol "Compressor volumetric efficiency [0..1]";

  // Effective valve K
  Real K_valve_eff "Effective valve K with opening fraction";

  // Effective viscosity (power-law non-Newtonian)
  // mu_eff = mu_L * (8*v/D)^(n-1)  — when n=1, mu_eff = mu_L (Newtonian)
  Real mu_eff_valve(unit="Pa.s") "Effective viscosity at valve";
  Real mu_eff_pipe1(unit="Pa.s") "Effective viscosity in pipe 1";
  Real mu_eff_pipe2(unit="Pa.s") "Effective viscosity in pipe 2";
  Real mu_eff_pipe3(unit="Pa.s") "Effective viscosity in pipe 3";
  Real mu_eff_pipe4(unit="Pa.s") "Effective viscosity in pipe 4";
  Real mu_eff_pipe5(unit="Pa.s") "Effective viscosity in pipe 5";

  // Two-phase flow factor (1.0 = pure liquid, 0.0 = fully gas-entrained)
  Real f_two_phase "Two-phase flow reduction factor [0..1]";

  // Output tracking
  Real V_transferred(unit="m3") "Cumulative transferred volume [m³]";
  Real V_transferred_gal "Transferred [gal]";
  Real V_liquid_gal "Remaining liquid [gal]";

  // Unit conversions
  parameter Real gal_per_m3 = 264.172;
  parameter Real Pa_per_psi = 6894.76;

initial equation
  V_liquid = V_liquid_0;
  m_gas = P_tank_0 * (V_tank - V_liquid_0) / (R_air * T_gas_0);

equation
  // =========================================================================
  // 1) GAS HEADSPACE
  // =========================================================================
  V_gas = V_tank - V_liquid;
  P_tank = m_gas * R_air * T_gas_0 / max(V_gas, 1e-6);
  P_gauge = P_tank - P_atm;
  P_tank_psig = P_gauge / Pa_per_psi;

  // =========================================================================
  // 2) LIQUID LEVEL IN HORIZONTAL CYLINDER
  // =========================================================================
  // V_liquid = L_tank_eff * A_cross_liquid(h)
  // A_cross(h) = R² * acos((R-h)/R) - (R-h)*sqrt(2*R*h - h²)
  // We need h from V_liquid: invert numerically via the algebraic equation
  //
  // For Modelica solver: state the algebraic relation
  //   V_liquid = L_tank_eff * (R_tank^2 * acos((R_tank - h_liquid)/R_tank)
  //              - (R_tank - h_liquid) * sqrt(max(2*R_tank*h_liquid - h_liquid^2, 0)))
  // =========================================================================

  // Clamp h_liquid to valid range
  A_cross_liquid = if h_liquid <= 0 then 0.0
    else if h_liquid >= D_tank then pi * R_tank * R_tank
    else R_tank * R_tank * acos((R_tank - h_liquid) / R_tank)
         - (R_tank - h_liquid) * sqrt(max(2*R_tank*h_liquid - h_liquid*h_liquid, 0));

  V_liquid = L_tank_eff * A_cross_liquid;

  // =========================================================================
  // 3) HYDROSTATIC HEAD AT OUTLET (liquid above outlet center-bottom)
  // =========================================================================
  // Outlet at bottom of tank => head = rho * g * h_liquid
  dP_head = rho_L * g_acc * h_liquid;

  // =========================================================================
  // 4) DRIVING PRESSURE
  // =========================================================================
  dP_drive = P_gauge + dP_head - (P_receiver - P_atm) - rho_L * g_acc * dz_total;

  // =========================================================================
  // 5a) TWO-PHASE END-OF-UNLOAD
  // =========================================================================
  // When liquid level drops below outlet diameter, air entrains into discharge.
  // Smooth cubic ramp: f=1 when h >= D_outlet, f->0 when h->0.
  // This effectively increases apparent resistance (divides driving pressure).
  f_two_phase = if h_liquid >= D_outlet then 1.0
    else if h_liquid <= 0 then 0.0
    else (h_liquid / D_outlet) * (h_liquid / D_outlet) * (3.0 - 2.0 * h_liquid / D_outlet);

  // =========================================================================
  // 5b) VALVE K MODEL
  // =========================================================================
  K_valve_eff = K_valve_open / max(u_valve * u_valve, 0.01);

  // =========================================================================
  // 6) PER-SEGMENT FLOW (series: same Q_L through all)
  // =========================================================================
  // Velocities
  v_valve = Q_L / max(A_valve, 1e-10);
  v_pipe1 = Q_L / max(A_pipe1, 1e-10);
  v_pipe2 = Q_L / max(A_pipe2, 1e-10);
  v_pipe3 = Q_L / max(A_pipe3, 1e-10);
  v_pipe4 = Q_L / max(A_pipe4, 1e-10);
  v_pipe5 = Q_L / max(A_pipe5, 1e-10);

  // Effective viscosity: power-law model  mu_eff = mu_L * (8v/D)^(n-1)
  // Shear rate gamma_dot = 8*v/D (pipe flow approximation)
  // When n=1: exponent=0, mu_eff = mu_L (Newtonian — no change)
  // Floor shear rate at 0.01 s^-1 to avoid 0^(n-1) singularity
  mu_eff_valve = mu_L * max(8.0 * abs(v_valve) / max(D_valve, 1e-6), 0.01) ^ (n_power_law - 1.0);
  mu_eff_pipe1 = mu_L * max(8.0 * abs(v_pipe1) / max(D_pipe1, 1e-6), 0.01) ^ (n_power_law - 1.0);
  mu_eff_pipe2 = mu_L * max(8.0 * abs(v_pipe2) / max(D_pipe2, 1e-6), 0.01) ^ (n_power_law - 1.0);
  mu_eff_pipe3 = mu_L * max(8.0 * abs(v_pipe3) / max(D_pipe3, 1e-6), 0.01) ^ (n_power_law - 1.0);
  mu_eff_pipe4 = mu_L * max(8.0 * abs(v_pipe4) / max(D_pipe4, 1e-6), 0.01) ^ (n_power_law - 1.0);
  mu_eff_pipe5 = mu_L * max(8.0 * abs(v_pipe5) / max(D_pipe5, 1e-6), 0.01) ^ (n_power_law - 1.0);

  // Reynolds numbers (using effective viscosity)
  Re_valve = rho_L * abs(v_valve) * D_valve / max(mu_eff_valve, 1e-10);
  Re_pipe1 = rho_L * abs(v_pipe1) * D_pipe1 / max(mu_eff_pipe1, 1e-10);
  Re_pipe2 = rho_L * abs(v_pipe2) * D_pipe2 / max(mu_eff_pipe2, 1e-10);
  Re_pipe3 = rho_L * abs(v_pipe3) * D_pipe3 / max(mu_eff_pipe3, 1e-10);
  Re_pipe4 = rho_L * abs(v_pipe4) * D_pipe4 / max(mu_eff_pipe4, 1e-10);
  Re_pipe5 = rho_L * abs(v_pipe5) * D_pipe5 / max(mu_eff_pipe5, 1e-10);

  // Friction factors with smooth laminar-turbulent blend
  f_pipe1 = smoothFriction(Re_pipe1, eps_pipe1, D_pipe1);
  f_pipe2 = smoothFriction(Re_pipe2, eps_pipe2, D_pipe2);
  f_pipe3 = smoothFriction(Re_pipe3, eps_pipe3, D_pipe3);
  f_pipe4 = smoothFriction(Re_pipe4, eps_pipe4, D_pipe4);
  f_pipe5 = smoothFriction(Re_pipe5, eps_pipe5, D_pipe5);

  // Pressure drops
  // Valve: minor loss only (L=0)
  dP_valve = K_valve_eff * (rho_L * v_valve * abs(v_valve) / 2.0);

  // Pipe 1: major + minor
  dP_seg1 = f_pipe1 * (L_pipe1/max(D_pipe1,1e-6)) * (rho_L * v_pipe1 * abs(v_pipe1) / 2.0)
           + K_pipe1 * (rho_L * v_pipe1 * abs(v_pipe1) / 2.0);

  // Pipe 2: major + minor
  dP_seg2 = f_pipe2 * (L_pipe2/max(D_pipe2,1e-6)) * (rho_L * v_pipe2 * abs(v_pipe2) / 2.0)
           + K_pipe2 * (rho_L * v_pipe2 * abs(v_pipe2) / 2.0);

  // Pipe 3: major + minor (zero when L_pipe3=0)
  dP_seg3 = f_pipe3 * (L_pipe3/max(D_pipe3,1e-6)) * (rho_L * v_pipe3 * abs(v_pipe3) / 2.0)
           + K_pipe3 * (rho_L * v_pipe3 * abs(v_pipe3) / 2.0);

  // Pipe 4: major + minor (zero when L_pipe4=0)
  dP_seg4 = f_pipe4 * (L_pipe4/max(D_pipe4,1e-6)) * (rho_L * v_pipe4 * abs(v_pipe4) / 2.0)
           + K_pipe4 * (rho_L * v_pipe4 * abs(v_pipe4) / 2.0);

  // Pipe 5: major + minor (zero when L_pipe5=0)
  dP_seg5 = f_pipe5 * (L_pipe5/max(D_pipe5,1e-6)) * (rho_L * v_pipe5 * abs(v_pipe5) / 2.0)
           + K_pipe5 * (rho_L * v_pipe5 * abs(v_pipe5) / 2.0);

  // Total loss
  dP_loss_total = dP_valve + dP_seg1 + dP_seg2 + dP_seg3 + dP_seg4 + dP_seg5;

  // =========================================================================
  // 7) FLOW EQUATION (algebraic: drive = loss)
  // =========================================================================
  // When dP_drive > 0 and liquid available, solve for Q_L such that
  // dP_drive = dP_loss_total.  If dP_drive <= 0, Q_L = 0.
  //
  // We state: dP_drive = dP_loss_total  when Q_L > 0
  //           Q_L = 0                    when dP_drive <= 0

  if dP_drive * f_two_phase > 0 and V_liquid > V_liquid_min and time >= t_valve_open then
    dP_drive * f_two_phase = dP_loss_total;
  else
    Q_L = 0;
  end if;

  // =========================================================================
  // 8) AIR INLET WITH COMPRESSOR CURVE & PRESSURE CONTROLLER
  // =========================================================================
  // Volumetric efficiency model: eta_v = 1 - c * (r^(1/gamma) - 1)
  // c_clearance = 0: constant flow (plant air / ideal compressor)
  // c_clearance = 0.02: rotary vane (PTO truck compressor)
  // c_clearance = 0.04: typical reciprocating portable compressor
  // c_clearance = 0.06: worn/cheap reciprocating compressor
  r_comp = max(P_tank / P_atm, 1.0);
  eta_vol = max(0.0, 1.0 - c_clearance * (r_comp^(1.0/gamma_air) - 1.0));

  // Mass flow with curve + soft ramp-down at P_max
  mdot_air_in = if P_tank < P_max_abs then
    mdot_air_max * eta_vol
  else
    mdot_air_max * eta_vol * max(0.0, 1.0 - (P_tank - P_max_abs) / 5000.0);

  // =========================================================================
  // 9) RELIEF VALVE
  // =========================================================================
  // Opens when P_tank > P_relief_abs, subsonic orifice flow to atmosphere
  mdot_relief = if P_tank > P_relief_abs then
    Cd_relief * A_relief * sqrt(max(2.0 * (P_tank - P_atm) * P_tank / (R_air * T_gas_0), 0))
  else
    0.0;

  // =========================================================================
  // 10) DIFFERENTIAL EQUATIONS
  // =========================================================================
  der(m_gas) = mdot_air_in - mdot_relief;
  der(V_liquid) = -Q_L;

  // =========================================================================
  // 11) OUTPUT VARIABLES
  // =========================================================================
  Q_L_gpm = Q_L * gal_per_m3 * 60.0;
  V_transferred = V_liquid_0 - V_liquid;
  V_transferred_gal = V_transferred * gal_per_m3;
  V_liquid_gal = V_liquid * gal_per_m3;

  annotation(
    experiment(StartTime=0, StopTime=7200, NumberOfIntervals=7200, Tolerance=1e-6),
    Documentation(info="<html>
      <p>Realistic tanker air-displacement unloading v2.</p>
      <p>Horizontal cylinder, multi-segment pipe, valve, relief.</p>
    </html>")
  );

end TankerTransferV2;

// =============================================================================
// HELPER FUNCTION: Smooth friction factor (laminar/transition/turbulent)
// =============================================================================
function smoothFriction
  "Darcy friction factor with smooth laminar-turbulent transition"
  input Real Re "Reynolds number";
  input Real eps "Pipe roughness [m]";
  input Real D "Pipe diameter [m]";
  output Real f "Darcy friction factor";
protected
  Real Re_safe;
  Real f_lam;
  Real f_turb;
  Real s;
  Real relRough;
algorithm
  Re_safe := max(abs(Re), 1.0);
  relRough := eps / max(D, 1e-6);

  // Laminar: f = 64/Re
  f_lam := 64.0 / Re_safe;

  // Turbulent: Swamee-Jain explicit approximation
  f_turb := 0.25 / (log10(relRough/3.7 + 5.74/(Re_safe^0.9)))^2;

  // Smooth blend between 2000 and 4000
  if Re_safe < 2000 then
    f := f_lam;
  elseif Re_safe > 4000 then
    f := f_turb;
  else
    s := (Re_safe - 2000) / 2000.0;
    // Cubic smoothstep
    s := s * s * (3.0 - 2.0 * s);
    f := (1.0 - s) * f_lam + s * f_turb;
  end if;
end smoothFriction;
