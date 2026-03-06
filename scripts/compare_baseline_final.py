#!/usr/bin/env python3
"""Compare original baseline vs final model (Tier 1+2) results."""
import csv

products = ['fleet_ocd', 'fleet_ethylene_glycol', 'fleet_resin_solution', 'fleet_tall_oil_rosin', 'fleet_perchloroethylene']
labels = {'fleet_ocd': 'OCD', 'fleet_ethylene_glycol': 'Ethylene Glycol', 'fleet_resin_solution': 'Resin Solution', 'fleet_tall_oil_rosin': 'Tall Oil Rosin', 'fleet_perchloroethylene': 'Perchloroethylene'}
visc = {'fleet_ocd': 0.6, 'fleet_ethylene_glycol': 16.1, 'fleet_resin_solution': 500, 'fleet_tall_oil_rosin': 5000, 'fleet_perchloroethylene': 9900}

base_ts = {'fleet_ocd':'20260306_164659','fleet_ethylene_glycol':'20260306_164715','fleet_resin_solution':'20260306_164728','fleet_tall_oil_rosin':'20260306_164746','fleet_perchloroethylene':'20260306_164806'}
final_ts = {'fleet_ocd':'20260306_174659','fleet_ethylene_glycol':'20260306_174708','fleet_resin_solution':'20260306_174715','fleet_tall_oil_rosin':'20260306_174723','fleet_perchloroethylene':'20260306_174734'}

def extract(csv_path):
    rows = []
    with open(csv_path) as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows.append([float(x) for x in row])
    h = {name: i for i, name in enumerate(header)}
    v0 = rows[0][h['V_liquid_gal']]
    threshold = v0 * 0.005
    comp_time = rows[-1][h['time']]
    for row in rows:
        if row[h['V_liquid_gal']] <= threshold:
            comp_time = row[h['time']]; break
    gpms = [r[h['Q_L_gpm']] for r in rows if r[h['time']] > 60 and r[h['Q_L_gpm']] > 0.01]
    avg_gpm = sum(gpms)/len(gpms) if gpms else 0
    peak_gpm = max(gpms) if gpms else 0
    mid_vol = v0 / 2
    p_mid = 0
    for row in rows:
        if row[h['V_liquid_gal']] <= mid_vol:
            p_mid = row[h['P_tank_psig']]; break
    p_final = rows[-1][h['P_tank_psig']]
    dp_start = 0; dp_end = 0
    for row in rows:
        if row[h['time']] >= 60 and dp_start == 0:
            dp_start = row[h['dP_drive']] / 6894.76
        if row[h['V_liquid_gal']] <= 200 and row[h['V_liquid_gal']] > 100:
            dp_end = row[h['dP_drive']] / 6894.76
    dp_loss_peak = 0
    for row in rows:
        if row[h['time']] >= 60:
            dp_loss_peak = row[h['dP_loss_total']] / 6894.76; break
    return {
        'time_min': comp_time/60.0, 'avg_gpm': avg_gpm, 'peak_gpm': peak_gpm,
        'p_mid_psig': p_mid, 'p_final_psig': p_final,
        'dp_start_psi': dp_start, 'dp_end_psi': dp_end,
        'dp_loss_peak_psi': dp_loss_peak,
    }

sep = '=' * 110
dash = '-' * 110

print(sep)
print('COMPREHENSIVE COMPARISON: Original Baseline  vs  Final Model (Tier 1+2)')
print('Original: 1-segment pipe (L=20ft, K=2.5), constant mu, no two-phase')
print('Final:    3-segment pipe (L=22ft, K=3.1), power-law mu, two-phase end-of-unload')
print(sep)

for prod in products:
    base_path = f'data/runs/{base_ts[prod]}_{prod}/outputs.csv'
    final_path = f'data/runs/{final_ts[prod]}_{prod}/outputs.csv'
    b = extract(base_path)
    f_ = extract(final_path)

    dt_pct = (f_['time_min'] - b['time_min']) / b['time_min'] * 100
    dg_pct = (f_['avg_gpm'] - b['avg_gpm']) / b['avg_gpm'] * 100

    print(f"\n{dash}")
    print(f"  {labels[prod]} ({visc[prod]} cP)")
    print(dash)
    print(f"  {'Metric':<30} {'BEFORE':>12} {'AFTER':>12} {'Change':>12}")
    print(f"  {'-'*30} {'-'*12} {'-'*12} {'-'*12}")
    print(f"  {'Completion time (min)':<30} {b['time_min']:>12.1f} {f_['time_min']:>12.1f} {dt_pct:>+11.1f}%")
    print(f"  {'Avg flow rate (GPM)':<30} {b['avg_gpm']:>12.1f} {f_['avg_gpm']:>12.1f} {dg_pct:>+11.1f}%")
    print(f"  {'Peak flow rate (GPM)':<30} {b['peak_gpm']:>12.1f} {f_['peak_gpm']:>12.1f} {(f_['peak_gpm']-b['peak_gpm'])/b['peak_gpm']*100:>+11.1f}%")
    print(f"  {'Pressure @ 50% (psig)':<30} {b['p_mid_psig']:>12.1f} {f_['p_mid_psig']:>12.1f} {f_['p_mid_psig']-b['p_mid_psig']:>+11.2f}")
    print(f"  {'dP_drive @ start (psi)':<30} {b['dp_start_psi']:>12.2f} {f_['dp_start_psi']:>12.2f} {f_['dp_start_psi']-b['dp_start_psi']:>+11.2f}")
    print(f"  {'dP_drive near end (psi)':<30} {b['dp_end_psi']:>12.2f} {f_['dp_end_psi']:>12.2f} {f_['dp_end_psi']-b['dp_end_psi']:>+11.2f}")
    print(f"  {'dP_loss @ peak (psi)':<30} {b['dp_loss_peak_psi']:>12.2f} {f_['dp_loss_peak_psi']:>12.2f} {f_['dp_loss_peak_psi']-b['dp_loss_peak_psi']:>+11.2f}")
    status_b = 'PASS' if b['time_min'] <= 90 else 'FAIL'
    status_f = 'PASS' if f_['time_min'] <= 90 else 'FAIL'
    print(f"  {'Status (< 90 min)':<30} {status_b:>12} {status_f:>12}")

print(f"\n{sep}")
print("SUMMARY OF MODEL CHANGES:")
print("  Tier 1A: K-fittings  -> +2 ft pipe, +0.6 K from itemized fittings")
print("  Tier 1B: Uncertainty -> +/-5-7% uncertainty in completion time (SCFM & viscosity dominant)")
print("  Tier 2A: Non-Newton. -> n_power_law param (default 1.0 = no effect on Newtonian products)")
print("  Tier 2B: Two-phase   -> flow taper in last ~90 gal when h_liquid < D_outlet")
print(sep)
