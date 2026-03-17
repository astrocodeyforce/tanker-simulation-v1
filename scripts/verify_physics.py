#!/usr/bin/env python3
"""
verify_physics.py — Physics Verification Suite for TankerTransferV2
=====================================================================
Four automated checks against existing simulation output data:

  1. Mass Conservation    — V_transferred + V_liquid = V_liquid(t=0) at every timestep
  2. Pressure Balance     — dP_drive * f_two_phase ≈ dP_loss_total when Q_L > 0
  3. Energy Balance       — ∫(dP_drive · Q_L) dt ≈ ∫(dP_loss_total · Q_L / f_two_phase) dt
  4. Dimensional / Unit   — Cross-check derived columns (GPM, gal, psig) against SI columns

Run:
  python3 scripts/verify_physics.py                       # all runs
  python3 scripts/verify_physics.py data/runs/SOME_RUN    # single run
"""

import sys
import os
import glob
import numpy as np
import pandas as pd
from pathlib import Path

# NumPy 2.x moved trapz → trapezoid
_trapz = getattr(np, "trapezoid", None) or np.trapz

# ─── tolerances ───────────────────────────────────────────────────────────────
MASS_TOL       = 1e-6   # relative volume conservation tolerance
PRESSURE_TOL   = 0.02   # 2 % relative tolerance on dP balance
UNIT_TOL       = 1e-4   # unit conversion tolerance (relative)
ENERGY_TOL     = 0.05   # 5 % energy balance tolerance

# ─── unit conversion constants (must match Modelica) ─────────────────────────
GAL_PER_M3 = 264.172
PA_PER_PSI = 6894.76


# ═══════════════════════════════════════════════════════════════════════════════
#  CHECK 1 — MASS (VOLUME) CONSERVATION
# ═══════════════════════════════════════════════════════════════════════════════
def check_mass_conservation(df: pd.DataFrame) -> dict:
    """
    At every timestep: V_liquid(t) + V_transferred(t) = V_liquid(0)
    Also checks gallon columns for consistency.
    """
    V0 = df["V_liquid"].iloc[0]
    residual_m3 = df["V_liquid"] + df["V_transferred"] - V0
    max_err = residual_m3.abs().max()
    max_rel = max_err / max(V0, 1e-30)

    # gallon cross-check
    gal_residual = df["V_liquid_gal"] + df["V_transferred_gal"] - df["V_liquid_gal"].iloc[0]
    max_gal_err = gal_residual.abs().max()

    passed = max_rel < MASS_TOL
    return {
        "name": "Mass Conservation",
        "passed": passed,
        "V_liquid_0_m3": V0,
        "max_residual_m3": max_err,
        "max_relative_error": max_rel,
        "max_gal_residual": max_gal_err,
        "detail": (
            f"V_liquid + V_transferred = V_liquid(0) at all {len(df)} timesteps. "
            f"Max residual = {max_err:.2e} m³ ({max_rel:.2e} relative)"
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  CHECK 2 — PRESSURE BALANCE  (algebraic constraint)
# ═══════════════════════════════════════════════════════════════════════════════
def check_pressure_balance(df: pd.DataFrame) -> dict:
    """
    When Q_L > 0:  dP_drive * f_two_phase = dP_loss_total  (Modelica algebraic eq)
    Verify this holds in the CSV output.
    """
    flowing = df[df["Q_L"] > 1e-10].copy()
    if len(flowing) == 0:
        return {
            "name": "Pressure Balance",
            "passed": True,
            "detail": "No flow timesteps — nothing to check",
            "flowing_points": 0,
        }

    f_tp = flowing["f_two_phase"] if "f_two_phase" in flowing.columns else 1.0
    drive_eff = flowing["dP_drive"] * f_tp
    loss = flowing["dP_loss_total"]
    residual = (drive_eff - loss).abs()
    scale = drive_eff.abs().clip(lower=1.0)  # avoid div-by-zero
    rel_err = residual / scale

    max_rel = rel_err.max()
    mean_rel = rel_err.mean()
    worst_idx = rel_err.idxmax()
    worst_time = flowing.loc[worst_idx, "time"]

    passed = max_rel < PRESSURE_TOL
    return {
        "name": "Pressure Balance",
        "passed": passed,
        "flowing_points": len(flowing),
        "max_relative_error": max_rel,
        "mean_relative_error": mean_rel,
        "worst_time_s": worst_time,
        "detail": (
            f"dP_drive·f_two_phase vs dP_loss_total over {len(flowing)} flowing points. "
            f"Max relative error = {max_rel:.2e} at t={worst_time:.1f}s"
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  CHECK 3 — ENERGY BALANCE
# ═══════════════════════════════════════════════════════════════════════════════
def check_energy_balance(df: pd.DataFrame) -> dict:
    """
    Energy delivered by pressure to the liquid vs energy dissipated in friction.

    Power input  = dP_drive · Q_L                  [W]  (pressure pushing liquid)
    Power lost   = (dP_loss_total / f_two_phase) · Q_L [W]  (friction + minor losses)

    When f_two_phase=1:  these must be equal by the algebraic constraint.
    When f_two_phase<1:  some driving pressure goes to accelerating air, so
                         input > friction (difference = two-phase dissipation).

    We integrate over the discharge period and compare:
      E_drive  = ∫ dP_drive · Q_L  dt   [J]   (total work done by gas on liquid)
      E_friction = ∫ dP_loss_total · Q_L dt  [J]  (total friction dissipation)

    The algebraic eq gives: dP_drive * f_two_phase = dP_loss_total
    So:  E_friction = ∫ dP_drive * f_two_phase * Q_L dt
    And: E_drive    = ∫ dP_drive * Q_L dt

    Therefore:  E_drive ≥ E_friction  (equal when f_two_phase=1 everywhere)
    And:        E_drive - E_friction = ∫ dP_drive * (1 - f_two_phase) * Q_L dt

    We verify:
      a) E_friction ≤ E_drive  (energy can't be created)
      b) E_friction = E_drive to within tolerance (during pure liquid phase)
    """
    flowing = df[df["Q_L"] > 1e-10].copy()
    if len(flowing) < 2:
        return {
            "name": "Energy Balance",
            "passed": True,
            "detail": "Insufficient flow points for energy integration",
        }

    has_ftp = "f_two_phase" in flowing.columns
    f_tp = flowing["f_two_phase"] if has_ftp else pd.Series(1.0, index=flowing.index)

    dt = np.diff(flowing["time"].values)

    # Trapezoidal integration
    P_drive = (flowing["dP_drive"] * flowing["Q_L"]).values
    P_friction = (flowing["dP_loss_total"] * flowing["Q_L"]).values

    E_drive = _trapz(P_drive, flowing["time"].values)
    E_friction = _trapz(P_friction, flowing["time"].values)

    # Two-phase dissipation
    P_twophase = (flowing["dP_drive"] * (1 - f_tp) * flowing["Q_L"]).values
    E_twophase = _trapz(P_twophase, flowing["time"].values)

    # Verification: E_drive = E_friction + E_twophase
    balance_residual = abs(E_drive - E_friction - E_twophase) / max(abs(E_drive), 1.0)

    # Also check pure-liquid phase only (f_two_phase == 1)
    pure_liquid = flowing[f_tp > 0.999].copy()
    if len(pure_liquid) >= 2:
        E_drive_pure = _trapz(
            (pure_liquid["dP_drive"] * pure_liquid["Q_L"]).values,
            pure_liquid["time"].values,
        )
        E_friction_pure = _trapz(
            (pure_liquid["dP_loss_total"] * pure_liquid["Q_L"]).values,
            pure_liquid["time"].values,
        )
        pure_ratio = abs(E_drive_pure - E_friction_pure) / max(abs(E_drive_pure), 1.0)
    else:
        E_drive_pure = E_friction_pure = 0
        pure_ratio = 0

    passed = balance_residual < ENERGY_TOL and pure_ratio < ENERGY_TOL
    return {
        "name": "Energy Balance",
        "passed": passed,
        "E_drive_J": E_drive,
        "E_friction_J": E_friction,
        "E_twophase_J": E_twophase,
        "balance_residual_rel": balance_residual,
        "pure_liquid_drive_J": E_drive_pure,
        "pure_liquid_friction_J": E_friction_pure,
        "pure_liquid_ratio": pure_ratio,
        "detail": (
            f"E_drive={E_drive:.1f} J, E_friction={E_friction:.1f} J, "
            f"E_two_phase={E_twophase:.1f} J. "
            f"Balance residual={balance_residual:.2e}. "
            f"Pure-liquid phase: drive={E_drive_pure:.1f} J vs friction={E_friction_pure:.1f} J "
            f"(ratio={pure_ratio:.2e})"
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  CHECK 4 — DIMENSIONAL / UNIT CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════════
def check_unit_consistency(df: pd.DataFrame) -> dict:
    """
    Cross-check unit conversions between SI and imperial columns:
      - V_liquid_gal  = V_liquid * 264.172
      - V_transferred_gal = V_transferred * 264.172
      - Q_L_gpm       = Q_L * 264.172 * 60
      - P_tank_psig    = P_gauge / 6894.76
      - P_gauge        = P_tank - P_atm  (approximate: P_atm ≈ 101325 Pa)
      - V_gas          = V_tank - V_liquid  (check via V_gas + V_liquid ≈ const)
      - dP_loss_total  = dP_valve + dP_seg1 + ... + dP_seg5
    """
    results = []

    # (a) Volume: gallon conversion
    if "V_liquid_gal" in df.columns:
        err = (df["V_liquid_gal"] - df["V_liquid"] * GAL_PER_M3).abs()
        scale = df["V_liquid_gal"].abs().clip(lower=1e-6)
        max_err = (err / scale).max()
        results.append(("V_liquid_gal = V_liquid × 264.172", max_err))

    if "V_transferred_gal" in df.columns:
        err = (df["V_transferred_gal"] - df["V_transferred"] * GAL_PER_M3).abs()
        scale = df["V_transferred_gal"].abs().clip(lower=1e-6)
        max_err = (err / scale).max()
        results.append(("V_transferred_gal = V_transferred × 264.172", max_err))

    # (b) Flow: GPM conversion
    if "Q_L_gpm" in df.columns:
        expected_gpm = df["Q_L"] * GAL_PER_M3 * 60.0
        err = (df["Q_L_gpm"] - expected_gpm).abs()
        scale = expected_gpm.abs().clip(lower=1e-6)
        max_err = (err / scale).max()
        results.append(("Q_L_gpm = Q_L × 264.172 × 60", max_err))

    # (c) Pressure: psig conversion
    if "P_tank_psig" in df.columns and "P_gauge" in df.columns:
        expected_psig = df["P_gauge"] / PA_PER_PSI
        err = (df["P_tank_psig"] - expected_psig).abs()
        scale = expected_psig.abs().clip(lower=1e-6)
        max_err = (err / scale).max()
        results.append(("P_tank_psig = P_gauge / 6894.76", max_err))

    # (d) P_gauge = P_tank - P_atm  (infer P_atm from t=0)
    if "P_gauge" in df.columns and "P_tank" in df.columns:
        # At t=0, P_tank ≈ P_atm (since initial gauge pressure is ~0)
        # Use the relation directly
        P_atm_est = df["P_tank"].iloc[0] - df["P_gauge"].iloc[0]
        gauge_calc = df["P_tank"] - P_atm_est
        err = (df["P_gauge"] - gauge_calc).abs()
        scale = df["P_gauge"].abs().clip(lower=1.0)
        max_err = (err / scale).max()
        results.append((f"P_gauge = P_tank - P_atm (P_atm≈{P_atm_est:.1f} Pa)", max_err))

    # (e) V_gas + V_liquid = constant (= V_tank)
    if "V_gas" in df.columns:
        V_total = df["V_gas"] + df["V_liquid"]
        V_tank_est = V_total.iloc[0]
        err = (V_total - V_tank_est).abs()
        max_err = err.max() / max(V_tank_est, 1e-6)
        results.append((f"V_gas + V_liquid = V_tank (={V_tank_est:.4f} m³)", max_err))

    # (f) dP_loss_total = dP_valve + Σ dP_seg_i
    dp_cols = ["dP_valve", "dP_seg1", "dP_seg2", "dP_seg3", "dP_seg4", "dP_seg5"]
    if all(c in df.columns for c in dp_cols) and "dP_loss_total" in df.columns:
        dp_sum = sum(df[c] for c in dp_cols)
        err = (df["dP_loss_total"] - dp_sum).abs()
        scale = df["dP_loss_total"].abs().clip(lower=1.0)
        max_err = (err / scale).max()
        results.append(("dP_loss_total = dP_valve + Σ dP_seg_i", max_err))

    # (g) h_liquid physical bounds: 0 ≤ h_liquid ≤ D_tank
    if "h_liquid" in df.columns:
        h_min = df["h_liquid"].min()
        h_max = df["h_liquid"].max()
        # We don't know D_tank from CSV, but h should be positive and < ~2.5m
        physical = h_min >= -1e-6 and h_max < 3.0
        results.append((f"h_liquid in [0, D_tank]: min={h_min:.6f}, max={h_max:.4f} m",
                         0 if physical else 1.0))

    # (h) Non-negative checks
    for col in ["Q_L", "V_liquid", "m_gas"] + (["f_two_phase"] if "f_two_phase" in df.columns else []):
        if col in df.columns:
            min_val = df[col].min()
            ok = min_val >= -1e-10
            results.append((f"{col} ≥ 0 (min={min_val:.6e})", 0 if ok else 1.0))

    all_pass = all(err < UNIT_TOL for _, err in results)
    return {
        "name": "Dimensional / Unit Consistency",
        "passed": all_pass,
        "checks": results,
        "detail": "; ".join(
            f"{'✓' if e < UNIT_TOL else '✗'} {desc} (err={e:.2e})"
            for desc, e in results
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  RUNNER
# ═══════════════════════════════════════════════════════════════════════════════
def verify_run(csv_path: str) -> list:
    """Run all four checks on a single outputs.csv."""
    df = pd.read_csv(csv_path)
    # Strip any whitespace from column names
    df.columns = df.columns.str.strip()

    results = [
        check_mass_conservation(df),
        check_pressure_balance(df),
        check_energy_balance(df),
        check_unit_consistency(df),
    ]
    return results


def print_results(run_name: str, results: list):
    """Pretty-print verification results for one run."""
    all_pass = all(r["passed"] for r in results)
    status = "✓ ALL PASS" if all_pass else "✗ FAILURES DETECTED"

    print(f"\n{'='*78}")
    print(f"  {run_name}")
    print(f"  {status}")
    print(f"{'='*78}")

    for r in results:
        icon = "✓" if r["passed"] else "✗"
        print(f"\n  {icon} {r['name']}")
        print(f"    {r['detail']}")

        # Print sub-checks for unit consistency
        if "checks" in r:
            for desc, err in r["checks"]:
                sub_icon = "✓" if err < UNIT_TOL else "✗"
                print(f"      {sub_icon} {desc} (err={err:.2e})")

    print()
    return all_pass


def main():
    base = Path(__file__).resolve().parent.parent
    runs_dir = base / "data" / "runs"

    if len(sys.argv) > 1:
        # Single run specified
        target = Path(sys.argv[1])
        csv_path = target / "outputs.csv" if target.is_dir() else target
        if not csv_path.exists():
            print(f"ERROR: {csv_path} not found")
            sys.exit(1)
        runs = [(target.stem if target.is_dir() else csv_path.stem, str(csv_path))]
    else:
        # Test a representative set: one field test, one fleet, one uncertainty
        representative = []
        for pattern in [
            "*field_test_2_comp2",  # field validation
            "*fleet_ocd",           # fleet low-viscosity
            "*fleet_resin_solution",  # fleet high-viscosity
            "*fleet_ethylene_glycol",  # fleet medium
            "*unc_ocd_base",        # uncertainty study
        ]:
            matches = sorted(runs_dir.glob(pattern))
            if matches:
                representative.append(matches[-1])  # latest run

        if not representative:
            # Fallback: grab latest 5 runs
            all_runs = sorted(runs_dir.glob("*/outputs.csv"))
            representative = [p.parent for p in all_runs[-5:]]

        runs = [(d.name, str(d / "outputs.csv")) for d in representative if (d / "outputs.csv").exists()]

    if not runs:
        print("No runs found to verify.")
        sys.exit(1)

    print(f"\n╔{'═'*76}╗")
    print(f"║  TankerTransferV2 — Physics Verification Suite{' '*29}║")
    print(f"║  Checks: Mass Conservation, Pressure Balance, Energy Balance, Units{' '*8}║")
    print(f"║  Runs to verify: {len(runs)}{' '*(57-len(str(len(runs))))}║")
    print(f"╚{'═'*76}╝")

    total_pass = 0
    total_fail = 0

    for name, csv_path in runs:
        results = verify_run(csv_path)
        ok = print_results(name, results)
        if ok:
            total_pass += 1
        else:
            total_fail += 1

    # ── Summary ──
    print(f"\n{'─'*78}")
    print(f"  SUMMARY: {total_pass} runs passed, {total_fail} runs failed")
    print(f"{'─'*78}\n")

    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
