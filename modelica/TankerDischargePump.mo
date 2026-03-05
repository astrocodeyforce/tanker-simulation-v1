// =============================================================================
// TankerDischargePump.mo — AODD Pump Variant of Tanker Unloading Model
// =============================================================================
// Tank is VENTED (atmospheric). Compressed air drives a positive-displacement
// diaphragm pump. Pump delivers constant flow at its air-limited capacity
// regardless of viscosity (up to pump's max pressure rating).
// =============================================================================

model TankerDischargePump
  "Tanker unloading with air-operated double-diaphragm (AODD) pump"

  constant Real R_air = 287.05;
  constant Real g_acc = 9.80665;
  constant Real pi = 3.14159265358979;

  parameter Real V_tank(unit="m3") = 26.498;
  parameter Real D_tank(unit="m") = 1.905;
  parameter Real L_tank(unit="m") = 0;

  parameter Real V_liquid_0(unit="m3") = 24.605;
  parameter Real P_atm(unit="Pa") = 101325.0;
  parameter Real T_gas_0(unit="K") = 293.15;

  parameter Real rho_L(unit="kg/m3") = 1000.0;
  parameter Real mu_L(unit="Pa.s") = 0.1;

  parameter Real D_valve(unit="m") = 0.0762;
  parameter Real K_valve_open(unit="1") = 0.2;
  parameter Real u_valve(unit="1") = 1.0;
  parameter Real D_pipe1(unit="m") = 0.0762;
  parameter Real L_pipe1(unit="m") = 8.0;
  parameter Real eps_pipe1(unit="m") = 1e-5;
  parameter Real K_pipe1(unit="1") = 1.0;
  parameter Real D_pipe2(unit="m") = 0.0762;
  parameter Real L_pipe2(unit="m") = 8.0;
  parameter Real eps_pipe2(unit="m") = 1e-5;
  parameter Real K_pipe2(unit="1") = 1.0;
  parameter Real dz_total(unit="m") = 0.0;
  parameter Real P_receiver(unit="Pa") = 101325.0;

  parameter Real V_liquid_min(unit="m3") = 0.038;

  // --- PUMP PARAMETER ---
  parameter Real Q_pump_max(unit="m3/s") = 2.9940e-3
    "Pump air-limited max flow [m3/s] (default: 47.5 GPM for 2-inch at 19 SCFM)";

  // DERIVED
  parameter Real R_tank = D_tank / 2.0;
  parameter Real L_tank_eff = if L_tank > 0 then L_tank
    else V_tank / (pi * R_tank * R_tank);
  parameter Real A_valve = pi * (D_valve/2)^2;
  parameter Real A_pipe1 = pi * (D_pipe1/2)^2;
  parameter Real A_pipe2 = pi * (D_pipe2/2)^2;
  parameter Real K_valve_eff = K_valve_open / max(u_valve * u_valve, 0.01);

  // STATE
  Real V_liquid(start=0, fixed=false, unit="m3");

  // ALGEBRAIC
  Real V_gas(unit="m3");
  Real h_liquid(unit="m");
  Real A_cross_liquid(unit="m2");
  Real dP_head(unit="Pa");
  Real dP_drive(unit="Pa");

  Real Q_L(unit="m3/s") "Actual flow rate (pump-limited)";
  Real Q_L_gpm;

  Real v_valve(unit="m/s");
  Real v_pipe1(unit="m/s");
  Real v_pipe2(unit="m/s");
  Real Re_valve, Re_pipe1, Re_pipe2;
  Real f_pipe1, f_pipe2;
  Real dP_valve(unit="Pa");
  Real dP_seg1(unit="Pa");
  Real dP_seg2(unit="Pa");
  Real dP_loss_total(unit="Pa");

  Real V_transferred(unit="m3");
  Real V_transferred_gal;
  Real V_liquid_gal;

  Real P_tank(unit="Pa");
  Real P_gauge(unit="Pa");
  Real P_tank_psig;
  Real m_gas(unit="kg");
  Real mdot_air_in(unit="kg/s");
  Real mdot_relief(unit="kg/s");

  parameter Real gal_per_m3 = 264.172;
  parameter Real Pa_per_psi = 6894.76;

initial equation
  V_liquid = V_liquid_0;

equation
  // Tank is vented - always atmospheric
  P_tank = P_atm;
  P_gauge = 0;
  P_tank_psig = 0;
  m_gas = P_atm * (V_tank - V_liquid) / (R_air * T_gas_0);
  mdot_air_in = 0;
  mdot_relief = 0;

  V_gas = V_tank - V_liquid;

  // Liquid level in horizontal cylinder
  A_cross_liquid = if h_liquid <= 0 then 0.0
    else if h_liquid >= D_tank then pi * R_tank * R_tank
    else R_tank * R_tank * acos((R_tank - h_liquid) / R_tank)
         - (R_tank - h_liquid) * sqrt(max(2*R_tank*h_liquid - h_liquid*h_liquid, 0));

  V_liquid = L_tank_eff * A_cross_liquid;

  dP_head = rho_L * g_acc * h_liquid;
  dP_drive = dP_head;

  // PUMP: positive displacement - constant flow at air-limited capacity
  // AODD pump delivers Q_pump_max regardless of viscosity
  Q_L = if V_liquid > V_liquid_min then Q_pump_max else 0;

  // Compute velocities and losses for output
  v_valve = Q_L / max(A_valve, 1e-10);
  v_pipe1 = Q_L / max(A_pipe1, 1e-10);
  v_pipe2 = Q_L / max(A_pipe2, 1e-10);
  Re_valve = rho_L * abs(v_valve) * D_valve / mu_L;
  Re_pipe1 = rho_L * abs(v_pipe1) * D_pipe1 / mu_L;
  Re_pipe2 = rho_L * abs(v_pipe2) * D_pipe2 / mu_L;
  f_pipe1 = smoothFriction(Re_pipe1, eps_pipe1, D_pipe1);
  f_pipe2 = smoothFriction(Re_pipe2, eps_pipe2, D_pipe2);
  dP_valve = K_valve_eff * (rho_L * v_valve * abs(v_valve) / 2.0);
  dP_seg1 = f_pipe1 * (L_pipe1/max(D_pipe1,1e-6)) * (rho_L * v_pipe1 * abs(v_pipe1) / 2.0)
            + K_pipe1 * (rho_L * v_pipe1 * abs(v_pipe1) / 2.0);
  dP_seg2 = f_pipe2 * (L_pipe2/max(D_pipe2,1e-6)) * (rho_L * v_pipe2 * abs(v_pipe2) / 2.0)
            + K_pipe2 * (rho_L * v_pipe2 * abs(v_pipe2) / 2.0);
  dP_loss_total = dP_valve + dP_seg1 + dP_seg2;

  // ODE
  der(V_liquid) = -Q_L;

  // Outputs
  Q_L_gpm = Q_L * gal_per_m3 * 60.0;
  V_transferred = V_liquid_0 - V_liquid;
  V_transferred_gal = V_transferred * gal_per_m3;
  V_liquid_gal = V_liquid * gal_per_m3;

  annotation(
    experiment(StartTime=0, StopTime=36000, NumberOfIntervals=36000, Tolerance=1e-6)
  );

end TankerDischargePump;

function smoothFriction
  input Real Re;
  input Real eps;
  input Real D;
  output Real f;
protected
  Real Re_safe, f_lam, f_turb, s, relRough;
algorithm
  Re_safe := max(abs(Re), 1.0);
  relRough := eps / max(D, 1e-6);
  f_lam := 64.0 / Re_safe;
  f_turb := 0.25 / (log10(relRough/3.7 + 5.74/(Re_safe^0.9)))^2;
  if Re_safe < 2000 then
    f := f_lam;
  elseif Re_safe > 4000 then
    f := f_turb;
  else
    s := (Re_safe - 2000) / 2000.0;
    s := s * s * (3.0 - 2.0 * s);
    f := (1.0 - s) * f_lam + s * f_turb;
  end if;
end smoothFriction;
