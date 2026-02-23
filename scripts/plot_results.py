#!/usr/bin/env python3
"""
plot_results.py — Visualization script for HelloWorld simulation output.

Reads the CSV output from OpenModelica simulation, generates a PNG plot,
and saves it to the outputs directory.

This script runs INSIDE the python-viz container.
"""

import sys
import os

OUTPUT_DIR = "/work/outputs"
CSV_FILE = os.path.join(OUTPUT_DIR, "HelloWorld_res.csv")
PNG_FILE = os.path.join(OUTPUT_DIR, "HelloWorld_plot.png")


def main():
    print("============================================")
    print(" Sim-Lab: Python Visualization Pipeline")
    print(f" Input:  {CSV_FILE}")
    print(f" Output: {PNG_FILE}")
    print("============================================")
    print()

    # ---- Validate input ----
    if not os.path.isfile(CSV_FILE):
        print(f"❌ ERROR: CSV file not found: {CSV_FILE}")
        print("   Did the OpenModelica simulation run first?")
        sys.exit(1)

    # ---- Import dependencies (installed at container startup) ----
    try:
        import pandas as pd
        import matplotlib
        matplotlib.use("Agg")  # Headless backend — no display server needed
        import matplotlib.pyplot as plt
    except ImportError as e:
        print(f"❌ ERROR: Missing dependency: {e}")
        print("   Run: pip install matplotlib pandas")
        sys.exit(1)

    # ---- Load data ----
    print("📦 Step 1: Loading CSV data...")
    try:
        df = pd.read_csv(CSV_FILE)
    except Exception as e:
        print(f"❌ ERROR: Failed to read CSV: {e}")
        sys.exit(1)

    print(f"   Loaded {len(df)} rows, {len(df.columns)} columns")
    print(f"   Columns: {list(df.columns)}")

    # ---- Find time and x columns ----
    # OpenModelica CSV may use 'time' or 'Time' as the column name
    time_col = None
    x_col = None

    for col in df.columns:
        col_clean = col.strip().strip('"')
        if col_clean.lower() == "time":
            time_col = col
        elif col_clean.lower() == "x":
            x_col = col

    if time_col is None:
        print("❌ ERROR: 'time' column not found in CSV")
        print(f"   Available columns: {list(df.columns)}")
        sys.exit(1)

    if x_col is None:
        print("❌ ERROR: 'x' column not found in CSV")
        print(f"   Available columns: {list(df.columns)}")
        sys.exit(1)

    print(f"   Using columns: time='{time_col}', x='{x_col}'")

    # ---- Generate plot ----
    print()
    print("📦 Step 2: Generating plot...")

    fig, ax = plt.subplots(figsize=(10, 6))

    time_data = df[time_col].astype(float)
    x_data = df[x_col].astype(float)

    ax.plot(time_data, x_data, "b-", linewidth=2, label="x(t) — simulated")

    # Plot exact solution for comparison: x(t) = exp(-t)
    import numpy as np
    t_exact = np.linspace(float(time_data.min()), float(time_data.max()), 200)
    x_exact = np.exp(-t_exact)
    ax.plot(t_exact, x_exact, "r--", linewidth=1.5, alpha=0.7, label="x(t) = e⁻ᵗ — exact")

    ax.set_xlabel("Time (s)", fontsize=12)
    ax.set_ylabel("x(t)", fontsize=12)
    ax.set_title("HelloWorld Validation — Exponential Decay\ndx/dt = -x, x(0) = 1", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Add annotation
    ax.annotate(
        "Sim-Lab Environment Validation\nModel: HelloWorld.mo",
        xy=(0.98, 0.98),
        xycoords="axes fraction",
        ha="right",
        va="top",
        fontsize=9,
        color="gray",
        style="italic",
    )

    plt.tight_layout()

    # ---- Save plot ----
    fig.savefig(PNG_FILE, dpi=150, bbox_inches="tight")
    plt.close(fig)

    file_size = os.path.getsize(PNG_FILE)
    print(f"✅ Step 2 Complete: {PNG_FILE} ({file_size:,} bytes)")

    print()
    print("============================================")
    print(" ✅ Visualization completed successfully")
    print(f" Output: {PNG_FILE}")
    print("============================================")


if __name__ == "__main__":
    main()
