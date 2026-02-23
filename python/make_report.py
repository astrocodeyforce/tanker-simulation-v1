#!/usr/bin/env python3
"""
make_report.py — Generate a summary comparison report across scenario runs.

Reads run_log.json from each run directory and produces a comparison table
as both text and optional HTML.

Usage (inside container):
    python /work/python/make_report.py /work/data/runs

Output:
    /work/data/runs/comparison_report.txt
    /work/data/runs/comparison_report.html (optional)
"""

import sys
import os
import json
import csv
from datetime import datetime


def load_run_log(run_dir):
    """Load run_log.json from a run directory."""
    log_path = os.path.join(run_dir, "run_log.json")
    if not os.path.isfile(log_path):
        return None
    with open(log_path) as f:
        return json.load(f)


def get_final_values(run_dir):
    """Read the last row of outputs.csv to extract final simulation values."""
    csv_path = os.path.join(run_dir, "outputs.csv")
    if not os.path.isfile(csv_path):
        return {}

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {}

    last = rows[-1]
    result = {}
    for key, val in last.items():
        key = key.strip().strip('"')
        try:
            result[key] = float(val)
        except ValueError:
            result[key] = val

    # Also get peak values
    peak_p = 0
    peak_q = 0
    for row in rows:
        p = float(row.get("P_tank_psig", row.get("P_tank", 0)))
        q = float(row.get("Q_total_gpm", row.get("Q_total", 0)))
        peak_p = max(peak_p, p)
        peak_q = max(peak_q, q)

    result["_peak_pressure"] = peak_p
    result["_peak_flow"] = peak_q
    result["_total_time_min"] = result.get("time", 0) / 60.0

    return result


def main():
    if len(sys.argv) < 2:
        runs_dir = "/work/data/runs"
    else:
        runs_dir = sys.argv[1]

    if not os.path.isdir(runs_dir):
        print(f"❌ ERROR: Runs directory not found: {runs_dir}")
        sys.exit(1)

    print("============================================")
    print(" TankerTransfer — Comparison Report")
    print("============================================")
    print()

    # Find all run directories
    run_dirs = sorted([
        os.path.join(runs_dir, d)
        for d in os.listdir(runs_dir)
        if os.path.isdir(os.path.join(runs_dir, d))
        and os.path.isfile(os.path.join(runs_dir, d, "run_log.json"))
    ])

    if not run_dirs:
        print("  No completed runs found.")
        sys.exit(0)

    print(f"  Found {len(run_dirs)} run(s)")
    print()

    # Collect data
    runs = []
    for rd in run_dirs:
        log = load_run_log(rd)
        finals = get_final_values(rd)
        if log:
            runs.append({
                "dir": os.path.basename(rd),
                "scenario": log.get("scenario", "unknown"),
                "timestamp": log.get("timestamp", ""),
                "status": log.get("status", "unknown"),
                "peak_pressure": finals.get("_peak_pressure", 0),
                "peak_flow": finals.get("_peak_flow", 0),
                "total_transferred": finals.get("V_transferred_gal", finals.get("V_transferred", 0)),
                "final_remaining": finals.get("V_liquid_gal", finals.get("V_liquid", 0)),
                "sim_time_min": finals.get("_total_time_min", 0),
            })

    # ---- Text report ----
    txt_lines = [
        "=" * 80,
        "TANKER TRANSFER — SCENARIO COMPARISON REPORT",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        "=" * 80,
        "",
    ]

    header = f"{'Scenario':<35} {'Peak P':>10} {'Peak Q':>10} {'Transferred':>12} {'Remaining':>12} {'Time':>8}"
    units = f"{'':35} {'(psig)':>10} {'(GPM)':>10} {'(gal)':>12} {'(gal)':>12} {'(min)':>8}"
    txt_lines.append(header)
    txt_lines.append(units)
    txt_lines.append("-" * 90)

    for r in runs:
        line = (
            f"{r['scenario']:<35} "
            f"{r['peak_pressure']:>10.2f} "
            f"{r['peak_flow']:>10.2f} "
            f"{r['total_transferred']:>12.1f} "
            f"{r['final_remaining']:>12.1f} "
            f"{r['sim_time_min']:>8.1f}"
        )
        txt_lines.append(line)

    txt_lines.append("-" * 90)
    txt_lines.append("")
    txt_lines.append("Notes:")
    txt_lines.append("  - Peak P: Maximum tank gauge pressure during simulation")
    txt_lines.append("  - Peak Q: Maximum instantaneous flow rate")
    txt_lines.append("  - Transferred: Total liquid delivered at end of simulation")
    txt_lines.append("  - Remaining: Liquid still in tank at end of simulation")
    txt_lines.append("  - Time: Total simulation time")

    txt_report = "\n".join(txt_lines)
    txt_path = os.path.join(runs_dir, "comparison_report.txt")
    with open(txt_path, "w") as f:
        f.write(txt_report)

    print(txt_report)
    print()
    print(f"  ✅ Text report saved: {txt_path}")

    # ---- HTML report ----
    html_path = os.path.join(runs_dir, "comparison_report.html")
    html = [
        "<!DOCTYPE html>",
        "<html><head><title>TankerTransfer Report</title>",
        "<style>",
        "  body { font-family: Arial, sans-serif; margin: 20px; }",
        "  table { border-collapse: collapse; width: 100%; }",
        "  th, td { border: 1px solid #ddd; padding: 8px; text-align: right; }",
        "  th { background-color: #4CAF50; color: white; }",
        "  tr:nth-child(even) { background-color: #f2f2f2; }",
        "  td:first-child { text-align: left; }",
        "  h1 { color: #333; }",
        "</style></head><body>",
        "<h1>TankerTransfer — Scenario Comparison</h1>",
        f"<p>Generated: {datetime.utcnow().isoformat()}Z</p>",
        "<table>",
        "<tr><th>Scenario</th><th>Peak P (psig)</th><th>Peak Q (GPM)</th>"
        "<th>Transferred (gal)</th><th>Remaining (gal)</th><th>Time (min)</th></tr>",
    ]

    for r in runs:
        html.append(
            f"<tr><td>{r['scenario']}</td>"
            f"<td>{r['peak_pressure']:.2f}</td>"
            f"<td>{r['peak_flow']:.2f}</td>"
            f"<td>{r['total_transferred']:.1f}</td>"
            f"<td>{r['final_remaining']:.1f}</td>"
            f"<td>{r['sim_time_min']:.1f}</td></tr>"
        )

    html.extend(["</table>", "</body></html>"])

    with open(html_path, "w") as f:
        f.write("\n".join(html))

    print(f"  ✅ HTML report saved: {html_path}")
    print()
    print("============================================")
    print(" ✅ Report generation complete")
    print("============================================")


if __name__ == "__main__":
    main()
