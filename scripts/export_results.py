#!/usr/bin/env python3
"""
export_results.py — Robust result extraction from OpenModelica output.

Handles both CSV and MAT (Modelica result) formats.
Extracts key variables and writes a clean CSV with standardized columns.

Usage (inside container):
    python /work/scripts/export_results.py <result_file> <output_csv>

Example:
    python /work/scripts/export_results.py /tmp/sim/TankerTransfer_res.csv /work/data/runs/.../outputs.csv
    python /work/scripts/export_results.py /tmp/sim/TankerTransfer_res.mat /work/data/runs/.../outputs.csv
"""

import sys
import os
import csv

# Variables we want in the output CSV (Modelica variable names)
TARGET_VARS = [
    "time",
    "P_tank_psig",
    "Q_total_gpm",
    "V_liquid_gal",
    "V_transferred_gal",
    "P_tank",
    "Q_pressure",
    "Q_pump_flow",
    "Q_total",
    "V_liquid",
    "V_transferred",
    "v_hose",
    "Re",
    "f_darcy",
    "dP_avail",
    "m_gas",
    "V_gas",
]

# Minimal required columns for the output CSV
REQUIRED_COLS = ["time", "P_tank_psig", "Q_total_gpm", "V_liquid_gal", "V_transferred_gal"]


def read_csv_result(filepath):
    """Read an OpenModelica CSV result file."""
    data = {}
    with open(filepath, "r") as f:
        reader = csv.reader(f)
        headers = next(reader)
        # Clean header names (may have quotes/spaces)
        headers = [h.strip().strip('"') for h in headers]
        for h in headers:
            data[h] = []
        for row in reader:
            for i, val in enumerate(row):
                try:
                    data[headers[i]].append(float(val.strip()))
                except (ValueError, IndexError):
                    data[headers[i]].append(0.0)
    return headers, data


def read_mat_result(filepath):
    """
    Read an OpenModelica MAT result file.
    Requires scipy (will fail gracefully if not available).
    """
    try:
        from scipy.io import loadmat
        import numpy as np
    except ImportError:
        print("ERROR: scipy not available — cannot read MAT files.")
        print("  Install with: pip install scipy")
        sys.exit(1)

    mat = loadmat(filepath)

    # OpenModelica MAT format:
    # 'name' = variable names (2D char array)
    # 'data_2' = time-varying data
    # 'dataInfo' = mapping info

    if "name" not in mat:
        print(f"ERROR: MAT file does not contain 'name' array: {filepath}")
        sys.exit(1)

    # Extract variable names
    names_raw = mat["name"]
    var_names = []
    for row in names_raw:
        name = "".join(chr(c) for c in row).strip()
        var_names.append(name)

    # Extract data
    data_2 = mat.get("data_2", None)
    if data_2 is None:
        print(f"ERROR: MAT file does not contain 'data_2': {filepath}")
        sys.exit(1)

    data_info = mat.get("dataInfo", None)

    headers = []
    data = {}

    # Try to map variables to data columns using dataInfo
    if data_info is not None:
        for i, name in enumerate(var_names):
            info = data_info[:, i] if i < data_info.shape[1] else None
            if info is not None and len(info) >= 2:
                table_idx = int(info[0])
                col_idx = abs(int(info[1])) - 1
                sign = 1 if int(info[1]) > 0 else -1
                if table_idx == 2 and col_idx < data_2.shape[0]:
                    headers.append(name)
                    data[name] = (sign * data_2[col_idx, :]).tolist()
    else:
        # Fallback: assume rows correspond to variables
        for i, name in enumerate(var_names):
            if i < data_2.shape[0]:
                headers.append(name)
                data[name] = data_2[i, :].tolist()

    return headers, data


def write_output_csv(data, output_path):
    """Write standardized output CSV with target variables."""
    # Determine which target variables are available
    available = [v for v in TARGET_VARS if v in data]
    missing_required = [v for v in REQUIRED_COLS if v not in data]

    if missing_required:
        print(f"WARNING: Missing required columns: {missing_required}")
        print(f"  Available: {list(data.keys())}")
        # Still write what we have

    if not available:
        print("ERROR: No target variables found in result data.")
        print(f"  Available variables: {list(data.keys())}")
        sys.exit(1)

    # Determine number of rows
    n_rows = len(data[available[0]])

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(available)
        for i in range(n_rows):
            row = [data[v][i] if i < len(data[v]) else 0.0 for v in available]
            writer.writerow(row)

    print(f"  Exported {n_rows} rows × {len(available)} columns → {output_path}")
    print(f"  Columns: {available}")
    return available


def main():
    if len(sys.argv) < 3:
        print("Usage: python export_results.py <result_file> <output_csv>")
        print("  Supported formats: .csv, .mat")
        sys.exit(2)

    result_file = sys.argv[1]
    output_csv = sys.argv[2]

    if not os.path.isfile(result_file):
        print(f"ERROR: Result file not found: {result_file}")
        sys.exit(1)

    print(f"  Reading: {result_file}")

    ext = os.path.splitext(result_file)[1].lower()
    if ext == ".csv":
        headers, data = read_csv_result(result_file)
    elif ext == ".mat":
        headers, data = read_mat_result(result_file)
    else:
        print(f"ERROR: Unsupported file format: {ext}")
        print("  Supported: .csv, .mat")
        sys.exit(1)

    print(f"  Found {len(headers)} variables, {len(data.get('time', []))} time steps")

    # Write output
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    write_output_csv(data, output_csv)


if __name__ == "__main__":
    main()
