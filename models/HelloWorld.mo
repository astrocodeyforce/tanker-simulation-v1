// =============================================================================
// HelloWorld.mo — Minimal Validation Model
// =============================================================================
// Purpose:
//   Validate that OpenModelica can compile, simulate, and export results.
//   This is NOT a physics/tanker model — it is a pipeline validation test.
//
// What it does:
//   Solves the ODE: dx/dt = -x, x(0) = 1
//   Exact solution: x(t) = e^(-t)
//   Simulates from t=0 to t=5 seconds.
//
// Expected output:
//   A CSV file with columns: time, x
//   x should decay exponentially from 1.0 toward 0.0
// =============================================================================

model HelloWorld
  "Minimal exponential decay model for pipeline validation"
  Real x(start = 1.0, fixed = true) "State variable — decays exponentially";
equation
  der(x) = -x "ODE: dx/dt = -x → solution: x(t) = exp(-t)";
  annotation(
    experiment(StartTime = 0, StopTime = 5, NumberOfIntervals = 500, Tolerance = 1e-6),
    Documentation(info = "<html><p>HelloWorld validation model for sim-lab environment.</p></html>")
  );
end HelloWorld;
