#!/usr/bin/env python3
"""Quick analysis of TankerTransferV2 CSV output."""
import csv, sys

filepath = sys.argv[1] if len(sys.argv) > 1 else "TankerTransferV2_res.csv"

with open(filepath) as f:
    reader = csv.DictReader(f, quoting=csv.QUOTE_ALL)
    rows = list(reader)

# Strip quotes from field names
clean = []
for r in rows:
    clean.append({k.strip('"'): v for k, v in r.items()})
rows = clean

print(f"Rows: {len(rows)}")
hdr = "  t(s)  P(psig)  Q(GPM)  Remain(gal)  Xferd(gal)  h(m)"
print(hdr)
print("-" * len(hdr))

checkpoints = [0, 600, 1200, 1800, 2400, 3000, 3600]
checkpoints = [i for i in checkpoints if i < len(rows)]
checkpoints.append(len(rows) - 1)

for i in checkpoints:
    r = rows[i]
    t = float(r["time"])
    P = float(r["P_tank_psig"])
    Q = float(r["Q_L_gpm"])
    V = float(r["V_liquid_gal"])
    X = float(r["V_transferred_gal"])
    h = float(r["h_liquid"])
    print(f"{t:6.0f}  {P:7.2f}  {Q:7.1f}  {V:11.0f}  {X:10.0f}  {h:5.3f}")

# Summary
peak_P = max(float(r["P_tank_psig"]) for r in rows)
peak_Q = max(float(r["Q_L_gpm"]) for r in rows)
final_X = float(rows[-1]["V_transferred_gal"])
print()
print(f"Peak pressure: {peak_P:.2f} psig")
print(f"Peak flow:     {peak_Q:.1f} GPM")
print(f"Total xferd:   {final_X:.0f} gal")
