#!/usr/bin/env python3
"""
plot_results.py — Generate 4-panel PNG plots from TankerTransfer simulation output.

Reads the CSV output and generates:
  - Top-left:     P_tank (psig) vs time (min)
  - Top-right:    Q_out (GPM) vs time (min)
  - Bottom-left:  V_remaining (gal) vs time (min)
  - Bottom-right: V_transferred (gal) vs time (min)

Usage (inside container):
    python /work/python/plot_results.py /work/data/runs/<run_dir>/outputs.csv

Output:
    Saves plots.png in the same directory as the input CSV.
"""

import sys
import os
import csv
import json


def load_csv(filepath):
    """Load CSV file into a dict of lists."""
    data = {}
    with open(filepath, "r") as f:
        reader = csv.reader(f)
        headers = [h.strip().strip('"') for h in next(reader)]
        for h in headers:
            data[h] = []
        for row in reader:
            for i, val in enumerate(row):
                if i < len(headers):
                    try:
                        data[headers[i]].append(float(val.strip()))
                    except ValueError:
                        data[headers[i]].append(0.0)
    return data


def find_column(data, candidates):
    """Find the first matching column name from a list of candidates."""
    for c in candidates:
        if c in data:
            return c
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_results.py <outputs.csv>")
        sys.exit(2)

    csv_file = sys.argv[1]
    if not os.path.isfile(csv_file):
        print(f"❌ ERROR: CSV file not found: {csv_file}")
        sys.exit(1)

    # Output PNG goes in the same directory
    run_dir = os.path.dirname(csv_file)
    png_file = os.path.join(run_dir, "plots.png")

    print("============================================")
    print(" TankerTransfer Visualization")
    print(f" Input:  {csv_file}")
    print(f" Output: {png_file}")
    print("============================================")
    print()

    # ---- Load data ----
    print("📦 Step 1: Loading CSV data...")
    data = load_csv(csv_file)
    n_rows = len(data.get("time", []))
    print(f"  Loaded {n_rows} rows")
    print(f"  Columns: {list(data.keys())}")

    # ---- Find columns ----
    time_col = find_column(data, ["time", "Time"])
    p_col = find_column(data, ["P_tank_psig", "P_tank"])
    q_col = find_column(data, ["Q_total_gpm", "Q_total"])
    vliq_col = find_column(data, ["V_liquid_gal", "V_liquid"])
    vtrans_col = find_column(data, ["V_transferred_gal", "V_transferred"])

    if not time_col:
        print("❌ ERROR: 'time' column not found")
        sys.exit(1)

    missing = []
    if not p_col:
        missing.append("P_tank_psig")
    if not q_col:
        missing.append("Q_total_gpm")
    if not vliq_col:
        missing.append("V_liquid_gal")
    if not vtrans_col:
        missing.append("V_transferred_gal")

    if missing:
        print(f"  ⚠️  Warning: missing columns: {missing}")
        print(f"  Available: {list(data.keys())}")

    # ---- Import plotting libraries ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
    except ImportError:
        print("❌ ERROR: matplotlib not available. Install with: pip install matplotlib")
        sys.exit(1)

    # ---- Extract time in minutes ----
    time_min = [t / 60.0 for t in data[time_col]]

    # ---- Determine units (check if we have _psig/_gpm/_gal variants) ----
    p_label = "P_tank (psig)" if "psig" in (p_col or "") else "P_tank (Pa)"
    q_label = "Flow Rate (GPM)" if "gpm" in (q_col or "") else "Flow Rate (m³/s)"
    vliq_label = "Remaining (gal)" if "gal" in (vliq_col or "") else "Remaining (m³)"
    vtrans_label = "Transferred (gal)" if "gal" in (vtrans_col or "") else "Transferred (m³)"

    # ---- Try to detect scenario name from run_log.json ----
    scenario_name = "TankerTransfer"
    run_log_path = os.path.join(run_dir, "run_log.json")
    if os.path.isfile(run_log_path):
        try:
            with open(run_log_path) as f:
                run_log = json.load(f)
            scenario_name = run_log.get("scenario", scenario_name)
        except Exception:
            pass

    # ---- Generate 4-panel plot ----
    print()
    print("📦 Step 2: Generating 4-panel plot...")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"TankerTransfer — {scenario_name}", fontsize=16, fontweight="bold")

    # --- Top-left: Tank Pressure ---
    ax = axes[0][0]
    if p_col and data.get(p_col):
        ax.plot(time_min, data[p_col], "b-", linewidth=1.5)
        ax.set_ylabel(p_label, fontsize=11)
        ax.axhline(y=30, color="r", linestyle="--", alpha=0.5, label="Max 30 psig")
        ax.legend(fontsize=9)
    else:
        ax.text(0.5, 0.5, "No pressure data", transform=ax.transAxes, ha="center")
    ax.set_xlabel("Time (min)", fontsize=11)
    ax.set_title("Tank Pressure", fontsize=12)
    ax.grid(True, alpha=0.3)

    # --- Top-right: Flow Rate ---
    ax = axes[0][1]
    if q_col and data.get(q_col):
        ax.plot(time_min, data[q_col], "g-", linewidth=1.5)
        ax.set_ylabel(q_label, fontsize=11)
    else:
        ax.text(0.5, 0.5, "No flow data", transform=ax.transAxes, ha="center")
    ax.set_xlabel("Time (min)", fontsize=11)
    ax.set_title("Liquid Flow Rate", fontsize=12)
    ax.grid(True, alpha=0.3)

    # --- Bottom-left: Volume Remaining ---
    ax = axes[1][0]
    if vliq_col and data.get(vliq_col):
        ax.plot(time_min, data[vliq_col], "m-", linewidth=1.5)
        ax.set_ylabel(vliq_label, fontsize=11)
    else:
        ax.text(0.5, 0.5, "No volume data", transform=ax.transAxes, ha="center")
    ax.set_xlabel("Time (min)", fontsize=11)
    ax.set_title("Liquid Remaining in Tank", fontsize=12)
    ax.grid(True, alpha=0.3)

    # --- Bottom-right: Volume Transferred ---
    ax = axes[1][1]
    if vtrans_col and data.get(vtrans_col):
        ax.plot(time_min, data[vtrans_col], "r-", linewidth=1.5)
        ax.set_ylabel(vtrans_label, fontsize=11)
    else:
        ax.text(0.5, 0.5, "No transfer data", transform=ax.transAxes, ha="center")
    ax.set_xlabel("Time (min)", fontsize=11)
    ax.set_title("Cumulative Transferred Volume", fontsize=12)
    ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(png_file, dpi=150, bbox_inches="tight")
    plt.close(fig)

    file_size = os.path.getsize(png_file)
    print(f"  ✅ Plot saved: {png_file} ({file_size:,} bytes)")

    # ---- Print summary stats ----
    print()
    print("📊 Summary Statistics:")
    if p_col and data.get(p_col):
        print(f"  Peak pressure:     {max(data[p_col]):.2f} {p_label.split('(')[1].rstrip(')')}")
    if q_col and data.get(q_col):
        print(f"  Peak flow rate:    {max(data[q_col]):.2f} {q_label.split('(')[1].rstrip(')')}")
    if vtrans_col and data.get(vtrans_col):
        print(f"  Total transferred: {data[vtrans_col][-1]:.1f} {vtrans_label.split('(')[1].rstrip(')')}")
    if vliq_col and data.get(vliq_col):
        print(f"  Final remaining:   {data[vliq_col][-1]:.1f} {vliq_label.split('(')[1].rstrip(')')}")
    if time_col:
        print(f"  Sim duration:      {data[time_col][-1]/60:.1f} min")

    print()
    print("============================================")
    print(" ✅ Visualization complete")
    print("============================================")


if __name__ == "__main__":
    main()
