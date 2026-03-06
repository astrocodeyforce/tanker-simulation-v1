#!/usr/bin/env python3
"""
export_results_v2.py — Extract key variables from TankerTransferV2 CSV output.

Usage:
    python3 export_results_v2.py <result_csv> <output_csv>
"""

import sys
import os
import csv

# Variables to extract from TankerTransferV2
TARGET_VARS = [
    "time",
    "P_tank_psig",
    "P_tank",
    "P_gauge",
    "Q_L",
    "Q_L_gpm",
    "V_liquid",
    "V_liquid_gal",
    "V_transferred",
    "V_transferred_gal",
    "V_gas",
    "h_liquid",
    "v_valve",
    "v_pipe1",
    "v_pipe2",
    "v_pipe3",
    "v_pipe4",
    "v_pipe5",
    "Re_valve",
    "Re_pipe1",
    "Re_pipe2",
    "Re_pipe3",
    "Re_pipe4",
    "Re_pipe5",
    "f_pipe1",
    "f_pipe2",
    "f_pipe3",
    "f_pipe4",
    "f_pipe5",
    "dP_valve",
    "dP_seg1",
    "dP_seg2",
    "dP_seg3",
    "dP_seg4",
    "dP_seg5",
    "dP_loss_total",
    "dP_drive",
    "dP_head",
    "mdot_air_in",
    "mdot_relief",
    "m_gas",
    "K_valve_eff",
]

REQUIRED = ["time", "P_tank_psig", "Q_L_gpm", "V_liquid_gal", "V_transferred_gal"]


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 export_results_v2.py <result_csv> <output_csv>")
        sys.exit(2)

    result_file = sys.argv[1]
    output_csv = sys.argv[2]

    if not os.path.isfile(result_file):
        print(f"ERROR: {result_file} not found")
        sys.exit(1)

    # Read OpenModelica CSV (headers may be quoted)
    data = {}
    with open(result_file) as f:
        reader = csv.reader(f)
        headers = [h.strip().strip('"') for h in next(reader)]
        for h in headers:
            data[h] = []
        for row in reader:
            for i, val in enumerate(row):
                try:
                    data[headers[i]].append(float(val.strip()))
                except (ValueError, IndexError):
                    data[headers[i]].append(0.0)

    available = [v for v in TARGET_VARS if v in data]
    missing_req = [v for v in REQUIRED if v not in data]

    if missing_req:
        print(f"WARNING: Missing required: {missing_req}")
        print(f"  Available: {sorted(data.keys())}")

    if not available:
        print("ERROR: No target variables found")
        sys.exit(1)

    n_rows = len(data[available[0]])
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(available)
        for i in range(n_rows):
            writer.writerow([data[v][i] for v in available])

    print(f"  Exported {n_rows} rows x {len(available)} cols -> {output_csv}")


if __name__ == "__main__":
    main()
