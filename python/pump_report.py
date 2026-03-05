#!/usr/bin/env python3
"""
Generate a professional multi-page pump suitability analysis PDF report.

4 pages:
  Page 1 — Title + Executive Summary + Verdict
  Page 2 — Pump Specs & Product Details (side-by-side tables)
  Page 3 — Failure Analysis (4 reasons, large readable text)
  Page 4 — Recommendation + Viscosity Performance Chart

Output: /work/data/downloads/Pump_Analysis_Report.pdf

Usage:
    python pump_report.py [output_path]
"""

import os
import sys
from datetime import datetime

# Determine output path
if len(sys.argv) > 1:
    OUTPUT_PATH = sys.argv[1]
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
    OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "downloads", "Pump_Analysis_Report.pdf")

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import FancyBboxPatch
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
NAVY = "#1a5276"
RED = "#c0392b"
GREEN = "#1e8449"
LIGHT_GREEN_BG = "#eafaf1"
LIGHT_RED_BG = "#fdedec"
LIGHT_BLUE_BG = "#eaf2f8"
GRAY = "#666666"
DARK = "#222222"
LIGHT_GRAY = "#cccccc"
DATE_STR = datetime.now().strftime("%B %d, %Y")


def _header(ax, title, subtitle=None):
    """Draw page header."""
    ax.text(0.5, 0.97, title, fontsize=22, fontweight="bold",
            ha="center", va="top", color=NAVY,
            fontfamily="sans-serif")
    if subtitle:
        ax.text(0.5, 0.935, subtitle, fontsize=13, ha="center", va="top",
                color=GRAY, style="italic")
    ax.plot([0.05, 0.95], [0.92, 0.92], color=NAVY, linewidth=2.5,
            transform=ax.transAxes)


def _footer(ax):
    """Draw page footer."""
    ax.plot([0.05, 0.95], [0.04, 0.04], color=LIGHT_GRAY, linewidth=0.8,
            transform=ax.transAxes)
    ax.text(0.5, 0.025, f"SIM-LAB  |  Bull & Bear Fleet  |  {DATE_STR}",
            fontsize=9, ha="center", color=GRAY)


def _wrap_text(ax, x, y, text, fontsize=12, color=DARK, max_chars=75,
               line_spacing=0.028, **kwargs):
    """Word-wrap text and draw. Returns the new y position."""
    words = text.split()
    line = ""
    for w in words:
        test = f"{line} {w}".strip()
        if len(test) > max_chars:
            ax.text(x, y, line, fontsize=fontsize, color=color,
                    fontfamily="sans-serif", **kwargs)
            y -= line_spacing
            line = w
        else:
            line = test
    if line:
        ax.text(x, y, line, fontsize=fontsize, color=color,
                fontfamily="sans-serif", **kwargs)
        y -= line_spacing
    return y


def _draw_table(ax, x, y, headers, rows, col_widths, fontsize=11):
    """Draw a simple table with header row."""
    header_h = 0.032
    row_h = 0.028
    total_w = sum(col_widths)

    # Header background
    hdr_box = FancyBboxPatch((x, y - header_h), total_w, header_h,
                              boxstyle="square,pad=0", facecolor=NAVY,
                              edgecolor=NAVY, transform=ax.transAxes)
    ax.add_patch(hdr_box)

    cx = x + 0.01
    for hi, hw in zip(headers, col_widths):
        ax.text(cx, y - header_h + 0.008, hi, fontsize=fontsize - 1,
                fontweight="bold", color="white", fontfamily="sans-serif")
        cx += hw

    y -= header_h
    for ri, row in enumerate(rows):
        bg = LIGHT_BLUE_BG if ri % 2 == 0 else "white"
        row_box = FancyBboxPatch((x, y - row_h), total_w, row_h,
                                  boxstyle="square,pad=0", facecolor=bg,
                                  edgecolor=LIGHT_GRAY, linewidth=0.5,
                                  transform=ax.transAxes)
        ax.add_patch(row_box)
        cx = x + 0.01
        for val, hw in zip(row, col_widths):
            ax.text(cx, y - row_h + 0.007, str(val), fontsize=fontsize - 1,
                    color=DARK, fontfamily="sans-serif")
            cx += hw
        y -= row_h

    return y


def page_1_title(pdf):
    """Page 1: Title + Executive Summary + Verdict."""
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    _header(ax, "PUMP SUITABILITY ANALYSIS",
            "Bull & Bear Fleet  --  Chemical Tanker Operations")

    y = 0.88

    # Big verdict box
    vbox = FancyBboxPatch((0.06, y - 0.09), 0.88, 0.09,
                           boxstyle="round,pad=0.01",
                           facecolor=LIGHT_RED_BG, edgecolor=RED,
                           linewidth=2.5, transform=ax.transAxes)
    ax.add_patch(vbox)
    ax.text(0.5, y - 0.025, "VERDICT:  NOT SUITABLE", fontsize=22,
            fontweight="bold", ha="center", color=RED)
    ax.text(0.5, y - 0.06, "Do NOT purchase this pump for chemical transfer service.",
            fontsize=13, ha="center", color=RED, style="italic")
    y -= 0.13

    # Executive Summary
    ax.text(0.06, y, "EXECUTIVE SUMMARY", fontsize=16, fontweight="bold", color=NAVY)
    y -= 0.015
    ax.plot([0.06, 0.94], [y, y], color=LIGHT_GRAY, linewidth=1)
    y -= 0.035

    summary_paras = [
        "This report evaluates whether the Predator 212cc (6.5 HP) centrifugal "
        "pump is suitable for unloading CALFOAM ES-302 (Sodium Laureth Sulfate) "
        "from tanker trucks in the Bull & Bear fleet.",

        "CALFOAM ES-302 has a viscosity of 200 to 2,000 cP depending on "
        "temperature. Centrifugal pumps are designed for water-like fluids "
        "below 50 cP. At the viscosities encountered in this application, "
        "the pump will deliver near-zero flow.",

        "Four critical failure modes were identified: viscosity mismatch, "
        "inability to self-prime thick fluids, dead-head overheating risk, "
        "and inadequate head after viscosity derating.",

        "The recommended alternative is a positive displacement pump "
        "(gear, lobe, or progressive cavity type), which maintains rated "
        "flow regardless of fluid viscosity."
    ]

    for para in summary_paras:
        y = _wrap_text(ax, 0.08, y, para, fontsize=12.5, max_chars=72,
                       line_spacing=0.027)
        y -= 0.015

    # Quick reference box
    y -= 0.01
    qbox = FancyBboxPatch((0.06, y - 0.18), 0.88, 0.18,
                           boxstyle="round,pad=0.01",
                           facecolor=LIGHT_BLUE_BG, edgecolor=NAVY,
                           linewidth=1.5, transform=ax.transAxes)
    ax.add_patch(qbox)
    ax.text(0.5, y - 0.02, "QUICK REFERENCE", fontsize=14,
            fontweight="bold", ha="center", color=NAVY)

    refs = [
        ("Pump", "Predator 212cc  /  6.5 HP  /  Centrifugal"),
        ("Product", "CALFOAM ES-302  /  SLES  /  200-2,000 cP"),
        ("Application", "Tanker unloading  /  gravity + air pressure"),
        ("Result", "FAIL  --  pump cannot move viscous fluids"),
        ("Alternative", "Positive displacement (gear / lobe / PC pump)"),
    ]
    ry = y - 0.05
    for label, value in refs:
        ax.text(0.10, ry, f"{label}:", fontsize=12, fontweight="bold", color=NAVY)
        ax.text(0.30, ry, value, fontsize=12, color=DARK)
        ry -= 0.028

    _footer(ax)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def page_2_specs(pdf):
    """Page 2: Pump Specifications & Product Details."""
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    _header(ax, "EQUIPMENT & PRODUCT DETAILS")

    y = 0.88

    # Pump specs table
    ax.text(0.06, y, "PUMP UNDER EVALUATION", fontsize=16,
            fontweight="bold", color=NAVY)
    y -= 0.015
    ax.plot([0.06, 0.94], [y, y], color=LIGHT_GRAY, linewidth=1)
    y -= 0.01

    pump_rows = [
        ("Model", "Predator 212cc (6.5 HP)"),
        ("Pump Type", "Centrifugal, single-stage"),
        ("Impeller", "Open or semi-open"),
        ("Engine", "Honda GX200 clone, 212cc, 4-stroke"),
        ("Speed", "3,600 RPM"),
        ("Rated Flow (water)", "~158 GPM at zero head"),
        ("Max Head (water)", "~85 ft"),
        ("Inlet / Outlet", '2" / 2" NPT'),
        ("Self-Priming", "Claimed (water only)"),
        ("Approximate Cost", "$150 - $250"),
    ]

    y = _draw_table(ax, 0.06, y,
                    ["Specification", "Value"],
                    pump_rows,
                    col_widths=[0.35, 0.53],
                    fontsize=12)

    y -= 0.04

    # Product specs table
    ax.text(0.06, y, "PRODUCT BEING TRANSFERRED", fontsize=16,
            fontweight="bold", color=NAVY)
    y -= 0.015
    ax.plot([0.06, 0.94], [y, y], color=LIGHT_GRAY, linewidth=1)
    y -= 0.01

    product_rows = [
        ("Product Name", "CALFOAM ES-302"),
        ("Chemical", "Sodium Laureth Sulfate (SLES)"),
        ("Viscosity Range", "200 - 2,000 cP"),
        ("Viscosity at 120F", "~200 - 500 cP"),
        ("Viscosity at Ambient", "~1,000 - 2,000 cP (gel-like)"),
        ("Specific Gravity", "1.04"),
        ("Loading Temperature", "120F"),
        ("Hazard Class", "Non-hazardous (surfactant)"),
        ("Typical Load", "~5,000 gallons / 43,400 lbs"),
    ]

    y = _draw_table(ax, 0.06, y,
                    ["Property", "Value"],
                    product_rows,
                    col_widths=[0.35, 0.53],
                    fontsize=12)

    y -= 0.04

    # Key insight box
    ibox = FancyBboxPatch((0.06, y - 0.10), 0.88, 0.10,
                           boxstyle="round,pad=0.01",
                           facecolor="#fef9e7", edgecolor="#f39c12",
                           linewidth=2, transform=ax.transAxes)
    ax.add_patch(ibox)
    ax.text(0.5, y - 0.02, "KEY INSIGHT", fontsize=14,
            fontweight="bold", ha="center", color="#e67e22")
    ax.text(0.5, y - 0.05, "CALFOAM ES-302 is 40x to 400x thicker than water.",
            fontsize=13, ha="center", color=DARK, fontweight="bold")
    ax.text(0.5, y - 0.08,
            "Water = 1 cP    |    CALFOAM at 120F ~ 200-500 cP    |    CALFOAM cold ~ 2,000 cP",
            fontsize=11, ha="center", color=GRAY)

    _footer(ax)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def page_3_failures(pdf):
    """Page 3: Four failure reasons with large readable text."""
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    _header(ax, "WHY THIS PUMP FAILS")

    y = 0.88

    failures = [
        ("1", "VISCOSITY MISMATCH",
         "Centrifugal pumps rely on spinning the fluid to generate pressure. "
         "This works for water (1 cP) and thin liquids (up to ~50 cP). "
         "CALFOAM ES-302 at 500-2,000 cP is far too thick -- the impeller "
         "simply churns without generating meaningful flow or pressure. "
         "Expected output: near ZERO gallons per minute."),

        ("2", "SELF-PRIMING FAILURE",
         "This pump is marketed as \"self-priming\" but that claim only "
         "applies to water. At 2,000 cP, the fluid resists being drawn "
         "through the suction line. The pump cannot create enough vacuum "
         "to overcome the fluid's internal resistance. The suction line "
         "remains empty while the pump runs dry."),

        ("3", "DEAD-HEAD & OVERHEATING",
         "When the fluid is too thick to move, the pump runs with zero "
         "flow (dead-headed). ALL input energy converts to heat. The "
         "mechanical seal will fail within minutes. A gasoline engine "
         "running next to overheated chemicals creates a serious fire "
         "and safety hazard."),

        ("4", "INADEQUATE HEAD AFTER DERATING",
         "The rated 85 ft of head applies to water only. Per Hydraulic "
         "Institute viscosity correction standards, head is reduced by "
         "60-80% at 1,000 cP. Effective head: only 17-34 ft. This is "
         "not enough to push through hoses, fittings, and elevation "
         "changes on a typical tanker unloading setup."),
    ]

    colors_num = ["#e74c3c", "#e67e22", "#8e44ad", "#2980b9"]

    for i, (num, title, desc) in enumerate(failures):
        # Number circle
        circle = plt.Circle((0.07, y - 0.01), 0.022, transform=ax.transAxes,
                            facecolor=colors_num[i], edgecolor="none")
        ax.add_patch(circle)
        ax.text(0.07, y - 0.012, num, fontsize=16, fontweight="bold",
                ha="center", va="center", color="white")

        # Title
        ax.text(0.11, y, title, fontsize=15, fontweight="bold",
                color=colors_num[i])
        y -= 0.035

        # Description
        y = _wrap_text(ax, 0.11, y, desc, fontsize=12, color=DARK,
                       max_chars=68, line_spacing=0.026)
        y -= 0.03

    # Bottom summary bar
    sbox = FancyBboxPatch((0.06, y - 0.06), 0.88, 0.06,
                           boxstyle="round,pad=0.01",
                           facecolor=LIGHT_RED_BG, edgecolor=RED,
                           linewidth=2, transform=ax.transAxes)
    ax.add_patch(sbox)
    ax.text(0.5, y - 0.025, "ALL FOUR FAILURE MODES APPLY TO THIS APPLICATION",
            fontsize=13, fontweight="bold", ha="center", color=RED)

    _footer(ax)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def page_4_recommendation(pdf):
    """Page 4: Recommendation + viscosity performance chart."""
    fig, ax_page = plt.subplots(figsize=(8.5, 11))
    ax_page.axis("off")
    ax_page.set_xlim(0, 1)
    ax_page.set_ylim(0, 1)

    _header(ax_page, "RECOMMENDATION & COMPARISON")

    y = 0.88

    # Recommendation box
    rbox = FancyBboxPatch((0.06, y - 0.14), 0.88, 0.14,
                           boxstyle="round,pad=0.01",
                           facecolor=LIGHT_GREEN_BG, edgecolor=GREEN,
                           linewidth=2.5, transform=ax_page.transAxes)
    ax_page.add_patch(rbox)

    ax_page.text(0.5, y - 0.02, "USE A POSITIVE DISPLACEMENT PUMP",
                 fontsize=18, fontweight="bold", ha="center", color=GREEN)
    ax_page.text(0.5, y - 0.055,
                 "Gear pumps, lobe pumps, and progressive cavity pumps",
                 fontsize=13, ha="center", color=DARK)
    ax_page.text(0.5, y - 0.08,
                 "maintain rated flow regardless of fluid viscosity.",
                 fontsize=13, ha="center", color=DARK)
    ax_page.text(0.5, y - 0.115,
                 "Example:  Viking SG-40 gear pump  |  2\" ports  |  "
                 "100 GPM at 2,000 cP  |  ~$2,500 - $4,000",
                 fontsize=11, ha="center", color=GRAY, style="italic")

    y -= 0.18

    # Comparison table
    ax_page.text(0.06, y, "PUMP TYPE COMPARISON", fontsize=16,
                 fontweight="bold", color=NAVY)
    y -= 0.015
    ax_page.plot([0.06, 0.94], [y, y], color=LIGHT_GRAY, linewidth=1)
    y -= 0.01

    comp_rows = [
        ("Centrifugal (Predator)", "0 - 5 GPM", "FAIL", "$150-250"),
        ("Gear Pump (Viking SG)", "80 - 100 GPM", "PASS", "$2,500-4,000"),
        ("Lobe Pump (Waukesha)", "50 - 150 GPM", "PASS", "$4,000-8,000"),
        ("Prog. Cavity (Moyno)", "50 - 200 GPM", "PASS", "$3,000-6,000"),
    ]

    y = _draw_table(ax_page, 0.06, y,
                    ["Pump Type", "Flow at 1000 cP", "Result", "Cost"],
                    comp_rows,
                    col_widths=[0.30, 0.22, 0.16, 0.20],
                    fontsize=11)

    y -= 0.03

    # Viscosity vs Flow chart (embedded)
    ax_chart = fig.add_axes([0.12, 0.10, 0.76, 0.28])  # [left, bottom, w, h]
    visc = np.array([1, 10, 50, 100, 200, 500, 1000, 2000])

    # Centrifugal performance curve (drops rapidly)
    cent_flow = np.array([158, 145, 100, 60, 25, 5, 1, 0])
    # Gear pump performance (nearly flat)
    gear_flow = np.array([100, 100, 100, 98, 95, 92, 88, 82])

    ax_chart.plot(visc, cent_flow, 'o-', color=RED, linewidth=2.5,
                  markersize=7, label="Centrifugal (Predator 212cc)")
    ax_chart.plot(visc, gear_flow, 's-', color=GREEN, linewidth=2.5,
                  markersize=7, label="Gear Pump (Viking SG-40)")

    # Shade the CALFOAM zone
    ax_chart.axvspan(200, 2000, alpha=0.12, color="#f0b27a",
                     label="CALFOAM ES-302 range")

    ax_chart.set_xscale("log")
    ax_chart.set_xlabel("Viscosity (cP)", fontsize=12, fontweight="bold")
    ax_chart.set_ylabel("Flow Rate (GPM)", fontsize=12, fontweight="bold")
    ax_chart.set_title("Flow Rate vs Viscosity  --  Centrifugal vs Gear Pump",
                       fontsize=13, fontweight="bold", color=NAVY, pad=10)
    ax_chart.legend(fontsize=10, loc="center left")
    ax_chart.set_xlim(1, 3000)
    ax_chart.set_ylim(0, 180)
    ax_chart.grid(True, alpha=0.3)
    ax_chart.tick_params(labelsize=10)

    # Annotate the CALFOAM zone
    ax_chart.annotate("CALFOAM\nzone", xy=(600, 150), fontsize=11,
                      fontweight="bold", color="#e67e22", ha="center")

    _footer(ax_page)
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def generate_with_matplotlib():
    """Generate the full 4-page report."""
    with PdfPages(OUTPUT_PATH) as pdf:
        page_1_title(pdf)
        page_2_specs(pdf)
        page_3_failures(pdf)
        page_4_recommendation(pdf)

    print(f"[pump_report] PDF saved: {OUTPUT_PATH}")
    print(f"[pump_report] Size: {os.path.getsize(OUTPUT_PATH):,} bytes")
    print(f"[pump_report] Pages: 4")


if __name__ == "__main__":
    if HAS_MPL:
        generate_with_matplotlib()
    else:
        print("[pump_report] matplotlib not found -- trying to install...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "--quiet", "matplotlib", "numpy"])
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        from matplotlib.patches import FancyBboxPatch
        import numpy as np
        generate_with_matplotlib()
