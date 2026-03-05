"""
TankerTransfer V2 — Unified Simulation Application
=====================================================

Full web application with:
  Page 1: Run Simulation  — input form, run button, live results
  Page 2: Past Results    — browse/compare previous runs
  Page 3: Engineering     — detailed pressure-drop / Reynolds analysis

Usage (via Docker Compose):
    docker compose up -d visual-dashboard
    # SSH tunnel: ssh -L 8501:localhost:8501 user@vps
    # Open: http://localhost:8501
"""

import os
import re
import io
import json
import glob
import time
import subprocess
import math
import base64
from pathlib import Path
from datetime import datetime, timezone

import yaml
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# =============================================================================
# CONFIGURATION
# =============================================================================

DATA_DIR = os.environ.get("DASHBOARD_DATA_DIR", "/work/data/runs")
CONFIG_DIR = "/work/config"
SCRIPTS_DIR = "/work/scripts"

COLORS = {
    "pressure": "#EF553B",
    "flow": "#636EFA",
    "remaining": "#00CC96",
    "transferred": "#AB63FA",
    "head": "#FFA15A",
    "valve": "#FF6692",
    "seg1": "#19D3F3",
    "seg2": "#B6E880",
    "seg3": "#FECB52",
    "seg4": "#FF97FF",
    "seg5": "#FFA15A",
}

# Pipe segment metadata for dynamic chart building
PIPE_SEGMENTS = [
    {"idx": 1, "re": "Re_pipe1", "dp": "dP_seg1", "color": "seg1", "label": "Pipe 1"},
    {"idx": 2, "re": "Re_pipe2", "dp": "dP_seg2", "color": "seg2", "label": "Pipe 2"},
    {"idx": 3, "re": "Re_pipe3", "dp": "dP_seg3", "color": "seg3", "label": "Pipe 3"},
    {"idx": 4, "re": "Re_pipe4", "dp": "dP_seg4", "color": "seg4", "label": "Pipe 4"},
    {"idx": 5, "re": "Re_pipe5", "dp": "dP_seg5", "color": "seg5", "label": "Pipe 5"},
]

PSI_CONV = 6894.76

# =============================================================================
# PRESETS — Quick-load parameter sets
# =============================================================================

PRESETS = {
    "Baseline — Latex (100 cP)": {
        "tank_total_volume_gal": 7000, "tank_diameter_in": 75.0, "tank_length_ft": 30.5,
        "initial_liquid_volume_gal": 6500, "initial_tank_pressure_psig": 0.0,
        "gas_temperature_C": 20.0, "ambient_pressure_psia": 14.696,
        "max_tank_pressure_psig": 25.0, "relief_valve_pressure_psig": 27.5,
        "relief_valve_Cd": 0.62, "relief_valve_diameter_in": 1.0,
        "air_supply_scfm": 19.0,
        "liquid_density_kg_m3": 1050.0, "liquid_viscosity_cP": 100.0,
        "valve_diameter_in": 3.0, "valve_K_open": 0.2, "valve_opening_fraction": 1.0,
        "num_pipes": 1,
        "pipe1_diameter_in": 3.0, "pipe1_length_ft": 20.0, "pipe1_roughness_mm": 0.01, "pipe1_K_minor": 2.5,
        "elevation_change_ft": 0.0, "receiver_pressure_psig": 0.0,
        "stop_time_s": 5400, "output_interval_s": 1.0, "min_liquid_volume_gal": 1.0,
    },
    "Solvent — Low Viscosity (1 cP)": {
        "tank_total_volume_gal": 7000, "tank_diameter_in": 75.0, "tank_length_ft": 30.5,
        "initial_liquid_volume_gal": 6500, "initial_tank_pressure_psig": 0.0,
        "gas_temperature_C": 20.0, "ambient_pressure_psia": 14.696,
        "max_tank_pressure_psig": 25.0, "relief_valve_pressure_psig": 27.5,
        "relief_valve_Cd": 0.62, "relief_valve_diameter_in": 1.0,
        "air_supply_scfm": 19.0,
        "liquid_density_kg_m3": 850.0, "liquid_viscosity_cP": 1.0,
        "valve_diameter_in": 3.0, "valve_K_open": 0.2, "valve_opening_fraction": 1.0,
        "num_pipes": 1,
        "pipe1_diameter_in": 3.0, "pipe1_length_ft": 20.0, "pipe1_roughness_mm": 0.01, "pipe1_K_minor": 2.5,
        "elevation_change_ft": 0.0, "receiver_pressure_psig": 0.0,
        "stop_time_s": 3600, "output_interval_s": 1.0, "min_liquid_volume_gal": 1.0,
    },
    "Coating — High Viscosity (500 cP)": {
        "tank_total_volume_gal": 7000, "tank_diameter_in": 75.0, "tank_length_ft": 30.5,
        "initial_liquid_volume_gal": 6500, "initial_tank_pressure_psig": 0.0,
        "gas_temperature_C": 20.0, "ambient_pressure_psia": 14.696,
        "max_tank_pressure_psig": 25.0, "relief_valve_pressure_psig": 27.5,
        "relief_valve_Cd": 0.62, "relief_valve_diameter_in": 1.0,
        "air_supply_scfm": 19.0,
        "liquid_density_kg_m3": 1200.0, "liquid_viscosity_cP": 500.0,
        "valve_diameter_in": 2.0, "valve_K_open": 0.3, "valve_opening_fraction": 1.0,
        "num_pipes": 2,
        "pipe1_diameter_in": 2.0, "pipe1_length_ft": 30.0, "pipe1_roughness_mm": 0.01, "pipe1_K_minor": 2.0,
        "pipe2_diameter_in": 2.0, "pipe2_length_ft": 30.0, "pipe2_roughness_mm": 0.01, "pipe2_K_minor": 1.5,
        "elevation_change_ft": 3.0, "receiver_pressure_psig": 0.0,
        "stop_time_s": 10800, "output_interval_s": 2.0, "min_liquid_volume_gal": 1.0,
    },
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def discover_runs(data_dir: str) -> list[dict]:
    """Scan for simulation run directories containing outputs.csv."""
    runs = []
    pattern = os.path.join(data_dir, "*", "outputs.csv")
    for csv_path in sorted(glob.glob(pattern)):
        run_dir = os.path.dirname(csv_path)
        run_name = os.path.basename(run_dir)
        log_path = os.path.join(run_dir, "run_log.json")
        metadata = {}
        if os.path.isfile(log_path):
            try:
                with open(log_path) as f:
                    metadata = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        scenario = metadata.get("scenario", run_name)
        runs.append({
            "name": run_name,
            "scenario": scenario,
            "timestamp": metadata.get("timestamp", ""),
            "csv_path": csv_path,
            "run_dir": run_dir,
            "metadata": metadata,
        })
    return runs


def load_csv(csv_path: str) -> pd.DataFrame:
    """Load simulation CSV and normalize column names."""
    df = pd.read_csv(csv_path)
    if "time" in df.columns:
        df["time_min"] = df["time"] / 60.0
    if "Q_L_gpm" in df.columns and "Q_total_gpm" not in df.columns:
        df["Q_total_gpm"] = df["Q_L_gpm"]
    return df


def generate_yaml_config(params: dict, scenario_name: str) -> str:
    """Generate a YAML config file string from parameter dict."""
    lines = [
        f"# Auto-generated by TankerTransfer V2 App",
        f"# {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"",
        f"scenario_name: {scenario_name}",
        f"",
        f"# Tank Geometry",
        f"tank_total_volume_gal: {params['tank_total_volume_gal']}",
        f"tank_diameter_in: {params['tank_diameter_in']}",
        f"tank_length_ft: {params['tank_length_ft']}",
        f"",
        f"# Initial Conditions",
        f"initial_liquid_volume_gal: {params['initial_liquid_volume_gal']}",
        f"initial_tank_pressure_psig: {params['initial_tank_pressure_psig']}",
        f"gas_temperature_C: {params['gas_temperature_C']}",
        f"ambient_pressure_psia: {params['ambient_pressure_psia']}",
        f"",
        f"# Pressure Limits",
        f"max_tank_pressure_psig: {params['max_tank_pressure_psig']}",
        f"relief_valve_pressure_psig: {params['relief_valve_pressure_psig']}",
        f"relief_valve_Cd: {params['relief_valve_Cd']}",
        f"relief_valve_diameter_in: {params['relief_valve_diameter_in']}",
        f"",
        f"# Air Supply",
        f"air_supply_scfm: {params['air_supply_scfm']}",
        f"",
        f"# Liquid Properties",
        f"liquid_density_kg_m3: {params['liquid_density_kg_m3']}",
        f"liquid_viscosity_cP: {params['liquid_viscosity_cP']}",
        f"",
        f"# Outlet Valve",
        f"valve_diameter_in: {params['valve_diameter_in']}",
        f"valve_K_open: {params['valve_K_open']}",
        f"valve_opening_fraction: {params['valve_opening_fraction']}",
        f"",
        f"# Pipe Segments (num_pipes: {int(params.get('num_pipes', 1))})",
        f"num_pipes: {int(params.get('num_pipes', 1))}",
        f"pipe1_diameter_in: {params['pipe1_diameter_in']}",
        f"pipe1_length_ft: {params['pipe1_length_ft']}",
        f"pipe1_roughness_mm: {params['pipe1_roughness_mm']}",
        f"pipe1_K_minor: {params['pipe1_K_minor']}",
        f"pipe2_diameter_in: {params.get('pipe2_diameter_in', 3.0)}",
        f"pipe2_length_ft: {params.get('pipe2_length_ft', 0.0)}",
        f"pipe2_roughness_mm: {params.get('pipe2_roughness_mm', 0.01)}",
        f"pipe2_K_minor: {params.get('pipe2_K_minor', 0.0)}",
        f"pipe3_diameter_in: {params.get('pipe3_diameter_in', 3.0)}",
        f"pipe3_length_ft: {params.get('pipe3_length_ft', 0.0)}",
        f"pipe3_roughness_mm: {params.get('pipe3_roughness_mm', 0.01)}",
        f"pipe3_K_minor: {params.get('pipe3_K_minor', 0.0)}",
        f"pipe4_diameter_in: {params.get('pipe4_diameter_in', 3.0)}",
        f"pipe4_length_ft: {params.get('pipe4_length_ft', 0.0)}",
        f"pipe4_roughness_mm: {params.get('pipe4_roughness_mm', 0.01)}",
        f"pipe4_K_minor: {params.get('pipe4_K_minor', 0.0)}",
        f"pipe5_diameter_in: {params.get('pipe5_diameter_in', 3.0)}",
        f"pipe5_length_ft: {params.get('pipe5_length_ft', 0.0)}",
        f"pipe5_roughness_mm: {params.get('pipe5_roughness_mm', 0.01)}",
        f"pipe5_K_minor: {params.get('pipe5_K_minor', 0.0)}",
        f"",
        f"# Elevation & Receiver",
        f"elevation_change_ft: {params['elevation_change_ft']}",
        f"receiver_pressure_psig: {params['receiver_pressure_psig']}",
        f"",
        f"# Simulation",
        f"stop_time_s: {int(params['stop_time_s'])}",
        f"output_interval_s: {params['output_interval_s']}",
        # Enforce a minimum floor of 1 gal for numerical stability —
        # prevents solver singularity when V_liquid → 0 exactly.
        f"min_liquid_volume_gal: {max(params['min_liquid_volume_gal'], 1.0)}",
    ]
    return "\n".join(lines)


def run_simulation(config_path: str) -> tuple[bool, str]:
    """
    Trigger the OpenModelica pipeline via Docker CLI.
    Returns (success, output_text).
    """
    # The dashboard runs inside a container, but has access to Docker socket.
    # We use docker CLI to run the simulation in the openmodelica-runner service.
    # --project-directory must point to the HOST path so volume mounts resolve.
    cmd = [
        "docker", "compose",
        "--project-directory", "/opt/sim-lab/truck-tanker-sim-env",
        "-f", "/work/docker-compose.yml",
        "--project-name", "simlab",
        "run", "--rm", "--entrypoint", "",
        "openmodelica-runner",
        "bash", "/work/scripts/run_scenario_v2.sh",
        f"/work/{config_path}",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,  # 15 min max
            cwd="/work",
        )
        output = result.stdout + "\n" + result.stderr
        success = result.returncode == 0
        return success, output
    except subprocess.TimeoutExpired:
        return False, "ERROR: Simulation timed out (15 min limit)"
    except Exception as e:
        return False, f"ERROR: {str(e)}"


def find_latest_run(scenario_prefix: str) -> str | None:
    """Find the most recent run directory matching a scenario prefix."""
    pattern = os.path.join(DATA_DIR, f"*{scenario_prefix}*", "outputs.csv")
    matches = sorted(glob.glob(pattern))
    if matches:
        return os.path.dirname(matches[-1])
    return None


# =============================================================================
# CHART BUILDERS
# =============================================================================


def build_pressure_chart(df, scenario=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"], y=df["P_tank_psig"],
        mode="lines", name="Tank Pressure",
        line=dict(color=COLORS["pressure"], width=2),
    ))
    fig.update_layout(
        title=f"Tank Pressure — {scenario}" if scenario else "Tank Pressure",
        xaxis_title="Time (min)", yaxis_title="Pressure (psig)",
        template="plotly_white", height=400,
    )
    return fig


def build_flow_chart(df, scenario=""):
    col = "Q_total_gpm" if "Q_total_gpm" in df.columns else "Q_L_gpm"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"], y=df[col],
        mode="lines", name="Flow Rate",
        line=dict(color=COLORS["flow"], width=2),
    ))
    fig.update_layout(
        title=f"Liquid Flow Rate — {scenario}" if scenario else "Liquid Flow Rate",
        xaxis_title="Time (min)", yaxis_title="Flow (GPM)",
        template="plotly_white", height=400,
    )
    return fig


def build_volume_remaining_chart(df, scenario=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"], y=df["V_liquid_gal"],
        mode="lines", name="Remaining",
        line=dict(color=COLORS["remaining"], width=2),
    ))
    fig.update_layout(
        title=f"Volume Remaining — {scenario}" if scenario else "Volume Remaining",
        xaxis_title="Time (min)", yaxis_title="Volume (gal)",
        template="plotly_white", height=400,
    )
    return fig


def build_volume_transferred_chart(df, scenario=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"], y=df["V_transferred_gal"],
        mode="lines", name="Transferred",
        line=dict(color=COLORS["transferred"], width=2),
    ))
    fig.update_layout(
        title=f"Volume Transferred — {scenario}" if scenario else "Volume Transferred",
        xaxis_title="Time (min)", yaxis_title="Volume (gal)",
        template="plotly_white", height=400,
    )
    return fig


def build_engineering_charts(df, scenario=""):
    """Build detailed engineering charts: pressure drops, Reynolds, level."""
    charts = []

    # Pressure drops — dynamic: only show active pipe segments
    if "dP_valve" in df.columns and "dP_seg1" in df.columns:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["time_min"], y=df["dP_valve"] / PSI_CONV,
            mode="lines", name="Valve", line=dict(color=COLORS["valve"])))
        for seg in PIPE_SEGMENTS:
            col = seg["dp"]
            if col in df.columns and df[col].abs().max() > 0.01:
                fig.add_trace(go.Scatter(x=df["time_min"], y=df[col] / PSI_CONV,
                    mode="lines", name=seg["label"], line=dict(color=COLORS[seg["color"]])))
        fig.update_layout(title="Pressure Drops by Component",
            xaxis_title="Time (min)", yaxis_title="ΔP (psi)",
            template="plotly_white", height=400)
        charts.append(fig)

    # Reynolds numbers — dynamic: only show segments with non-zero pressure drop
    re_plotted = False
    fig = go.Figure()
    for seg in PIPE_SEGMENTS:
        col = seg["re"]
        dp_col = seg["dp"]
        # A pipe is "active" when its pressure-drop column has significant values
        active = (dp_col in df.columns and df[dp_col].abs().max() > 0.01)
        if col in df.columns and active:
            fig.add_trace(go.Scatter(x=df["time_min"], y=df[col],
                mode="lines", name=seg["label"], line=dict(color=COLORS[seg["color"]])))
            re_plotted = True
    if re_plotted:
        fig.add_hline(y=2300, line_dash="dash", line_color="red",
            annotation_text="Laminar→Transition")
        fig.add_hline(y=4000, line_dash="dash", line_color="orange",
            annotation_text="Transition→Turbulent")
        fig.update_layout(title="Reynolds Number",
            xaxis_title="Time (min)", yaxis_title="Re",
            template="plotly_white", height=400)
        charts.append(fig)

    # Liquid level
    if "h_liquid" in df.columns:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["time_min"],
            y=df["h_liquid"] * 39.3701,  # m → inches
            mode="lines", name="Liquid Level",
            line=dict(color=COLORS["remaining"], width=2)))
        fig.update_layout(title="Liquid Level in Tank",
            xaxis_title="Time (min)", yaxis_title="Height (inches)",
            template="plotly_white", height=400)
        charts.append(fig)

    # Air mass flow
    if "mdot_air_in" in df.columns:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["time_min"], y=df["mdot_air_in"] * 1000,
            mode="lines", name="Compressor In",
            line=dict(color=COLORS["flow"], width=2)))
        if "mdot_relief" in df.columns:
            fig.add_trace(go.Scatter(x=df["time_min"], y=df["mdot_relief"] * 1000,
                mode="lines", name="Relief Out",
                line=dict(color=COLORS["pressure"], width=2)))
        fig.update_layout(title="Air Mass Flow",
            xaxis_title="Time (min)", yaxis_title="Flow (g/s)",
            template="plotly_white", height=400)
        charts.append(fig)

    return charts


# =============================================================================
# PDF REPORT GENERATOR
# =============================================================================


def generate_pdf_report(
    df: pd.DataFrame,
    scenario: str,
    summary: dict,
    params: dict | None = None,
) -> bytes:
    """Generate a PDF report with all simulation charts and metrics.

    Uses Plotly's kaleido engine to export charts as images, then assembles
    them into a multi-page PDF using matplotlib.  Called on-demand only.

    Returns PDF as bytes (ready for st.download_button).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.table import Table

    buf = io.BytesIO()

    with PdfPages(buf) as pdf:
        # ==== PAGE 1: Title + Summary + Parameters ====
        fig_page, ax = plt.subplots(figsize=(11, 8.5))  # landscape letter
        ax.axis("off")

        # Company logo (if exists)
        logo_path = Path("/work/data/assets/logo.png")
        if not logo_path.exists():
            for ext in ("jpg", "jpeg", "svg", "webp"):
                alt = logo_path.with_suffix(f".{ext}")
                if alt.exists():
                    logo_path = alt
                    break
        if logo_path.exists() and logo_path.suffix != ".svg":
            try:
                logo_img = plt.imread(str(logo_path))
                logo_ax = fig_page.add_axes([0.02, 0.85, 0.15, 0.12])
                logo_ax.imshow(logo_img)
                logo_ax.axis("off")
            except Exception:
                pass

        # Title
        ax.text(0.5, 0.92, "Tanker Unloading Simulation Report",
                ha="center", va="top", fontsize=22, fontweight="bold")
        ax.text(0.5, 0.87, f"Scenario: {scenario}",
                ha="center", va="top", fontsize=14, color="#444")
        ax.text(0.5, 0.83, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                ha="center", va="top", fontsize=10, color="#888")

        # Summary metrics table
        ax.text(0.5, 0.76, "Key Metrics", ha="center", va="top",
                fontsize=14, fontweight="bold")
        summary_items = list(summary.items())
        cell_data = [[k, str(v)] for k, v in summary_items]
        tbl = ax.table(
            cellText=cell_data,
            colLabels=["Metric", "Value"],
            loc="center",
            cellLoc="center",
            bbox=[0.15, 0.40, 0.70, 0.34],
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(11)
        for key, cell in tbl.get_celld().items():
            if key[0] == 0:
                cell.set_facecolor("#2C3E50")
                cell.set_text_props(color="white", fontweight="bold")
            else:
                cell.set_facecolor("#F8F9FA" if key[0] % 2 == 0 else "white")
            cell.set_edgecolor("#DEE2E6")

        # Parameters table (if provided)
        if params:
            ax.text(0.5, 0.36, "Simulation Parameters", ha="center", va="top",
                    fontsize=14, fontweight="bold")
            # Select key parameters to show
            key_params = [
                ("Tank Volume (gal)", params.get("tank_total_volume_gal", "—")),
                ("Liquid Volume (gal)", params.get("initial_liquid_volume_gal", "—")),
                ("Density (kg/m³)", params.get("liquid_density_kg_m3", "—")),
                ("Viscosity (cP)", params.get("liquid_viscosity_cP", "—")),
                ("Air Supply (SCFM)", params.get("air_supply_scfm", "—")),
                ("Max Pressure (psig)", params.get("max_tank_pressure_psig", "—")),
                ("Valve Diameter (in)", params.get("valve_diameter_in", "—")),
                ("Pipe 1", f"{params.get('pipe1_diameter_in', '—')}\" × {params.get('pipe1_length_ft', '—')} ft"),
            ]
            # Add pipe2-5 only if active
            for i in range(2, 6):
                L = params.get(f"pipe{i}_length_ft", 0)
                if L and float(L) > 0:
                    key_params.append((
                        f"Pipe {i}",
                        f"{params.get(f'pipe{i}_diameter_in', '—')}\" × {L} ft"
                    ))

            param_data = [[k, str(v)] for k, v in key_params]
            tbl2 = ax.table(
                cellText=param_data,
                colLabels=["Parameter", "Value"],
                loc="center",
                cellLoc="center",
                bbox=[0.15, 0.02, 0.70, min(0.32, 0.04 * (len(param_data) + 1))],
            )
            tbl2.auto_set_font_size(False)
            tbl2.set_fontsize(10)
            for key, cell in tbl2.get_celld().items():
                if key[0] == 0:
                    cell.set_facecolor("#2C3E50")
                    cell.set_text_props(color="white", fontweight="bold")
                else:
                    cell.set_facecolor("#F8F9FA" if key[0] % 2 == 0 else "white")
                cell.set_edgecolor("#DEE2E6")

        pdf.savefig(fig_page, dpi=150)
        plt.close(fig_page)

        # ==== CHART PAGES ====
        # Collect all chart figures
        all_figs = [
            ("Tank Pressure", build_pressure_chart(df, scenario)),
            ("Liquid Flow Rate", build_flow_chart(df, scenario)),
            ("Volume Remaining", build_volume_remaining_chart(df, scenario)),
            ("Volume Transferred", build_volume_transferred_chart(df, scenario)),
        ]
        eng_figs = build_engineering_charts(df, scenario)
        for ef in eng_figs:
            title = ef.layout.title.text if ef.layout.title and ef.layout.title.text else "Engineering Detail"
            all_figs.append((title, ef))

        # Render 2 charts per page
        for i in range(0, len(all_figs), 2):
            fig_page, axes = plt.subplots(2, 1, figsize=(11, 8.5))
            for j, ax in enumerate(axes):
                idx = i + j
                if idx < len(all_figs):
                    chart_title, plotly_fig = all_figs[idx]
                    try:
                        img_bytes = plotly_fig.to_image(
                            format="png", width=1000, height=400, scale=2
                        )
                        from PIL import Image
                        img = Image.open(io.BytesIO(img_bytes))
                        ax.imshow(img)
                        ax.axis("off")
                    except Exception as e:
                        ax.text(0.5, 0.5, f"Chart unavailable: {chart_title}\n{e}",
                                ha="center", va="center", fontsize=12, color="red")
                        ax.axis("off")
                else:
                    ax.axis("off")

            fig_page.tight_layout(pad=0.5)
            pdf.savefig(fig_page, dpi=150)
            plt.close(fig_page)

    buf.seek(0)
    return buf.read()


def compute_summary(df: pd.DataFrame) -> dict:
    """Compute key summary metrics from simulation results."""
    col_q = "Q_total_gpm" if "Q_total_gpm" in df.columns else "Q_L_gpm"
    summary = {}
    summary["Peak Flow (GPM)"] = f"{df[col_q].max():.1f}"
    summary["Peak Pressure (psig)"] = f"{df['P_tank_psig'].max():.1f}"
    summary["Total Transferred (gal)"] = f"{df['V_transferred_gal'].iloc[-1]:.0f}"
    summary["Final Remaining (gal)"] = f"{df['V_liquid_gal'].iloc[-1]:.0f}"

    # Find time when flow effectively stops (< 1 GPM)
    # Must find where flow drops below 1 GPM AFTER it was flowing (>1 GPM),
    # to skip the initial zero-flow pressurization period.
    flow = df[col_q]
    was_flowing = (flow > 1.0).cummax()  # True once flow has exceeded 1 GPM
    stopped = was_flowing & (flow < 1.0)  # True after flow started AND dropped back below 1
    if stopped.any():
        t = df.loc[stopped.idxmax(), "time_min"]
        summary["Transfer Time (min)"] = f"{t:.1f}"
    else:
        t = df['time_min'].iloc[-1]
        summary["Transfer Time (min)"] = f"{t:.1f} (still flowing)"

    if "Re_pipe1" in df.columns:
        re_max = df["Re_pipe1"].max()
        if re_max > 4000:
            regime = f"Turbulent (Re={re_max:,.0f})"
        elif re_max > 2300:
            regime = f"Transition (Re={re_max:,.0f})"
        else:
            regime = f"Laminar (Re={re_max:,.0f})"
        summary["Flow Regime"] = regime

    return summary


def trim_to_completion(df: pd.DataFrame) -> pd.DataFrame:
    """Trim simulation data to the meaningful window.

    Logic:
    1. Find when flow stops (tank empty).
    2. After that, find when pressure reaches the relief/max limit.
    3. Trim dataframe to that point + a small margin.
    If flow never stops, return the full dataframe.
    """
    col_q = "Q_total_gpm" if "Q_total_gpm" in df.columns else "Q_L_gpm"
    flow = df[col_q]
    pressure = df["P_tank_psig"]

    # Step 1: Find when flow stops after it started
    was_flowing = (flow > 1.0).cummax()
    stopped = was_flowing & (flow < 1.0)
    if not stopped.any():
        return df  # Still flowing — show everything

    stop_idx = stopped.idxmax()

    # Step 2: After flow stops, find when pressure reaches its max
    # (relief valve limit or max_tank_pressure)
    post_flow = df.loc[stop_idx:]
    if len(post_flow) < 2:
        return df

    # Find peak pressure after flow stops
    p_max_post = post_flow["P_tank_psig"].max()
    # Find where it first reaches within 95% of that peak
    # (accounts for relief valve oscillation)
    threshold = p_max_post * 0.95
    reached = post_flow[post_flow["P_tank_psig"] >= threshold]
    if reached.empty:
        return df

    end_idx = reached.index[0]

    # Add 1-minute margin after reaching pressure limit
    end_time = df.loc[end_idx, "time_min"] + 1.0
    trimmed = df[df["time_min"] <= end_time]

    # Safety: never return less than the transfer portion
    if len(trimmed) < len(df.loc[:stop_idx]):
        return df.loc[:stop_idx]

    return trimmed


def calc_pressurization_time(
    tank_capacity_gal: float,
    liquid_volume_gal: float,
    target_psig: float,
    compressor_scfm: float,
) -> float:
    """Calculate minutes to pressurize the tank headspace from 0 to target_psig.

    Uses ideal gas:  SCF_needed = V_headspace_ft3 × (target_psig / 14.696)
    Time = SCF_needed / SCFM
    """
    if target_psig <= 0 or compressor_scfm <= 0:
        return 0.0
    headspace_gal = max(tank_capacity_gal - liquid_volume_gal, 0)
    headspace_ft3 = headspace_gal / 7.48052
    scf_needed = headspace_ft3 * (target_psig / 14.696)
    return scf_needed / compressor_scfm


# =============================================================================
# PAGE: RUN SIMULATION
# =============================================================================


def page_run_simulation():
    st.header("Run Simulation")
    st.markdown("Configure parameters and run the OpenModelica physics simulation.")

    # ---- Preset selector ----
    col_preset, col_name = st.columns([2, 2])
    with col_preset:
        preset_choice = st.selectbox(
            "Load Preset",
            ["Custom"] + list(PRESETS.keys()),
            help="Load a predefined parameter set, or start from scratch",
        )
    with col_name:
        default_name = "custom_run"
        if preset_choice != "Custom":
            default_name = preset_choice.split("—")[0].strip().lower().replace(" ", "_")
        run_name = st.text_input("Run Name", value=default_name,
            help="Short identifier for this simulation run")

    # Get defaults from preset or use baseline
    if preset_choice != "Custom" and preset_choice in PRESETS:
        defaults = PRESETS[preset_choice]
    else:
        defaults = PRESETS["Baseline — Latex (100 cP)"]

    st.divider()

    # ---- Input Form ----
    # Using columns for compact layout
    tab_tank, tab_liquid, tab_air, tab_valve, tab_pipe, tab_discharge, tab_sim = st.tabs([
        "🛢️ Tank", "💧 Liquid", "💨 Air Supply", "🔧 Valve",
        "🔩 Piping", "📐 Discharge", "⚙️ Simulation"
    ])

    params = {}

    with tab_tank:
        st.subheader("Tank Geometry")
        st.caption("Standard DOT-407 horizontal cylinder tanker truck")
        c1, c2, c3 = st.columns(3)
        params["tank_total_volume_gal"] = c1.number_input(
            "Tank Capacity (gallons)", min_value=100, max_value=15000,
            value=int(defaults["tank_total_volume_gal"]), step=100,
            help="Total tank size. Standard tanker trucks are 5,000–9,000 gal.")
        params["tank_diameter_in"] = c2.number_input(
            "Tank Diameter (inches)", min_value=12.0, max_value=120.0,
            value=float(defaults["tank_diameter_in"]), step=1.0, format="%.1f",
            help="Cross-section diameter of the cylindrical tank.")
        params["tank_length_ft"] = c3.number_input(
            "Tank Length (feet)", min_value=0.0, max_value=60.0,
            value=float(defaults["tank_length_ft"]), step=1.0, format="%.1f",
            help="Length of the cylinder. Set to 0 to auto-calculate from capacity & diameter.")

        st.subheader("Starting Conditions")
        st.caption("How full is the tank and what's the pressure when we start?")
        c1, c2, c3 = st.columns(3)
        params["initial_liquid_volume_gal"] = c1.number_input(
            "Liquid in Tank (gallons)", min_value=0, max_value=15000,
            value=int(defaults["initial_liquid_volume_gal"]), step=100,
            help="How much liquid is in the tank at the start. Typically 90–95% of capacity.")
        params["initial_tank_pressure_psig"] = c2.number_input(
            "Starting Pressure (psig)", min_value=0.0, max_value=50.0,
            value=float(defaults["initial_tank_pressure_psig"]), step=0.5, format="%.1f",
            help="Air pressure inside the tank before pumping starts. Usually 0 (atmospheric).")
        params["gas_temperature_C"] = c3.number_input(
            "Air Temperature (°C)", min_value=-20.0, max_value=60.0,
            value=float(defaults["gas_temperature_C"]), step=1.0, format="%.1f",
            help="Temperature of the air space above the liquid. 20°C = 68°F (room temp).")
        params["ambient_pressure_psia"] = st.number_input(
            "Outside Air Pressure (psia)", min_value=10.0, max_value=16.0,
            value=float(defaults["ambient_pressure_psia"]), step=0.01, format="%.3f",
            help="Atmospheric pressure. 14.696 is standard sea level. Lower at higher elevations.")

        st.subheader("Safety — Overpressure Protection")
        st.caption("The relief valve is a safety device that automatically vents air if tank pressure gets too high, preventing rupture.")
        c1, c2, c3, c4 = st.columns(4)
        params["max_tank_pressure_psig"] = c1.number_input(
            "Target Max Pressure (psig)", min_value=1.0, max_value=100.0,
            value=float(defaults["max_tank_pressure_psig"]), step=1.0, format="%.1f",
            help="The compressor stops adding air when the tank reaches this pressure. DOT-407 standard: 25 psig.")
        params["relief_valve_pressure_psig"] = c2.number_input(
            "Relief Valve Opens At (psig)", min_value=1.0, max_value=100.0,
            value=float(defaults["relief_valve_pressure_psig"]), step=0.5, format="%.1f",
            help="If pressure exceeds this, the safety valve opens to release air. Typically set 10% above max pressure.")
        params["relief_valve_Cd"] = c3.number_input(
            "Relief Valve Efficiency", min_value=0.1, max_value=1.0,
            value=float(defaults["relief_valve_Cd"]), step=0.01, format="%.2f",
            help="How efficiently the relief valve vents air (0–1 scale). 0.62 is the industry standard for most valves.")
        params["relief_valve_diameter_in"] = c4.number_input(
            "Relief Valve Size (inches)", min_value=0.25, max_value=4.0,
            value=float(defaults["relief_valve_diameter_in"]), step=0.25, format="%.2f",
            help="Opening diameter of the relief valve. Larger = can vent more air. 1 inch is standard.")

    with tab_liquid:
        st.subheader("What Liquid Are You Pumping?")
        c1, c2, c3 = st.columns(3)
        params["liquid_density_kg_m3"] = c1.number_input(
            "Density (kg/m³)", min_value=500.0, max_value=2000.0,
            value=float(defaults["liquid_density_kg_m3"]), step=10.0, format="%.1f",
            help="Weight per volume. Water = 1000. Heavier liquids need more pressure to push.")
        # Show specific gravity as a convenience — auto-calculated from density
        sg_value = params["liquid_density_kg_m3"] / 1000.0
        c2.metric("Specific Gravity (SG)", f"{sg_value:.3f}",
            help="SG = Density ÷ 1000.  Water = 1.000.  This is auto-calculated from the density you entered.")
        params["liquid_viscosity_cP"] = c3.number_input(
            "Viscosity — How Thick? (cP)", min_value=0.1, max_value=5000.0,
            value=float(defaults["liquid_viscosity_cP"]), step=1.0, format="%.1f",
            help="Viscosity = resistance to flow. Water = 1 cP, Honey ≈ 3000 cP. Thicker liquids flow slower and need more pressure.")

        st.info("""
        **Pick values from this table based on your liquid:**
        | Liquid | Density (kg/m³) | SG | Viscosity (cP) |
        |--------|----------------|------|-------------------|
        | Water | 1000 | 1.000 | 1 |
        | Solvent (acetone, MEK) | 850 | 0.850 | 0.5–2 |
        | Latex paint | 1050 | 1.050 | 50–200 |
        | Thick coating / adhesive | 1200 | 1.200 | 300–1000 |
        | Motor oil (SAE 30) | 880 | 0.880 | 200–400 |
        | Honey | 1400 | 1.400 | 2000–3000 |
        
        *SG (Specific Gravity) = how much heavier than water. SG of 1.05 means 5% heavier than water.*
        """)

    with tab_air:
        st.subheader("Air Compressor")
        st.caption("The compressor pumps air into the tank to push the liquid out through the pipe.")
        params["air_supply_scfm"] = st.number_input(
            "Compressor Output (SCFM)", min_value=1.0, max_value=200.0,
            value=float(defaults["air_supply_scfm"]), step=1.0, format="%.1f",
            help="How much air the compressor delivers per minute. Higher = faster tank pressurization.")
        st.info("""
        **How much air does your compressor put out?**
        - Truck-mounted (PTO-driven): **12–25 SCFM** ← most common for tanker unloading
        - Small portable: **5–15 SCFM**
        - Industrial / plant air: **50–200 SCFM**
        
        *SCFM = Standard Cubic Feet per Minute (air volume at normal atmospheric conditions)*
        """)

    with tab_valve:
        st.subheader("Outlet Valve")
        st.caption("The valve at the bottom of the tank that controls liquid flow out.")
        c1, c2, c3 = st.columns(3)
        params["valve_diameter_in"] = c1.number_input(
            "Valve Size (inches)", min_value=0.5, max_value=6.0,
            value=float(defaults["valve_diameter_in"]), step=0.5, format="%.1f",
            help="Inside diameter of the valve opening. Should match your pipe size.")
        params["valve_K_open"] = c2.number_input(
            "Valve Resistance Factor", min_value=0.01, max_value=10.0,
            value=float(defaults["valve_K_open"]), step=0.1, format="%.2f",
            help="How much the valve restricts flow (lower = less restriction). Ball valve: 0.05–0.2, Gate: 0.1–0.3, Butterfly: 0.3–1.5")
        params["valve_opening_fraction"] = c3.number_input(
            "How Far Open (0–1)", min_value=0.05, max_value=1.0,
            value=float(defaults["valve_opening_fraction"]), step=0.05, format="%.2f",
            help="1.0 = fully open, 0.5 = half open. Partially closing reduces flow rate.")

    with tab_pipe:
        st.caption("The hose/pipe from the tank to the receiving vessel. Add pipe segments for each distinct section of your piping run.")

        num_pipes = st.number_input(
            "🔧 Number of Pipe Segments", min_value=1, max_value=5,
            value=int(defaults.get("num_pipes", 1)), step=1,
            key="num_pipes",
            help="How many distinct pipe/hose sections between the tank and receiver? Default is 1. Add more if diameter or material changes along the run.")
        params["num_pipes"] = num_pipes

        # --- Pipe Segment 1 (always shown) ---
        st.subheader("Pipe Segment 1")
        c1, c2, c3, c4 = st.columns(4)
        params["pipe1_diameter_in"] = c1.number_input(
            "Pipe Diameter (in)", min_value=0.5, max_value=8.0,
            value=float(defaults["pipe1_diameter_in"]), step=0.5, format="%.1f",
            key="p1d", help="Inside diameter of the hose/pipe. Common sizes: 2\", 3\", 4\".")
        params["pipe1_length_ft"] = c2.number_input(
            "Hose Length (ft)", min_value=1.0, max_value=200.0,
            value=float(defaults["pipe1_length_ft"]), step=5.0, format="%.1f",
            key="p1l", help="Total length of this pipe/hose section.")
        params["pipe1_roughness_mm"] = c3.number_input(
            "Wall Roughness (mm)", min_value=0.001, max_value=1.0,
            value=float(defaults["pipe1_roughness_mm"]), step=0.01, format="%.3f",
            key="p1r", help="How rough the inside wall is. Smooth rubber hose ≈ 0.01, Steel pipe ≈ 0.045, Rusty pipe ≈ 0.5")
        params["pipe1_K_minor"] = c4.number_input(
            "Fittings Resistance", min_value=0.0, max_value=20.0,
            value=float(defaults["pipe1_K_minor"]), step=0.5, format="%.1f",
            key="p1k", help="Add up resistance values for all elbows, couplings, and fittings in this section. See table below.")

        # --- Pipe Segment 2 ---
        if num_pipes >= 2:
            st.subheader("Pipe Segment 2")
            c1, c2, c3, c4 = st.columns(4)
            params["pipe2_diameter_in"] = c1.number_input(
                "Pipe Diameter (in)", min_value=0.5, max_value=8.0,
                value=float(defaults.get("pipe2_diameter_in", 3.0)), step=0.5, format="%.1f",
                key="p2d")
            params["pipe2_length_ft"] = c2.number_input(
                "Hose Length (ft)", min_value=1.0, max_value=200.0,
                value=float(defaults.get("pipe2_length_ft", 25.0)), step=5.0, format="%.1f",
                key="p2l")
            params["pipe2_roughness_mm"] = c3.number_input(
                "Wall Roughness (mm)", min_value=0.001, max_value=1.0,
                value=float(defaults.get("pipe2_roughness_mm", 0.01)), step=0.01, format="%.3f",
                key="p2r")
            params["pipe2_K_minor"] = c4.number_input(
                "Fittings Resistance", min_value=0.0, max_value=20.0,
                value=float(defaults.get("pipe2_K_minor", 1.0)), step=0.5, format="%.1f",
                key="p2k")
        else:
            params["pipe2_diameter_in"] = 3.0
            params["pipe2_length_ft"] = 0.0
            params["pipe2_roughness_mm"] = 0.01
            params["pipe2_K_minor"] = 0.0

        # --- Pipe Segment 3 ---
        if num_pipes >= 3:
            st.subheader("Pipe Segment 3")
            c1, c2, c3, c4 = st.columns(4)
            params["pipe3_diameter_in"] = c1.number_input(
                "Pipe Diameter (in)", min_value=0.5, max_value=8.0,
                value=float(defaults.get("pipe3_diameter_in", 3.0)), step=0.5, format="%.1f",
                key="p3d")
            params["pipe3_length_ft"] = c2.number_input(
                "Hose Length (ft)", min_value=1.0, max_value=200.0,
                value=float(defaults.get("pipe3_length_ft", 25.0)), step=5.0, format="%.1f",
                key="p3l")
            params["pipe3_roughness_mm"] = c3.number_input(
                "Wall Roughness (mm)", min_value=0.001, max_value=1.0,
                value=float(defaults.get("pipe3_roughness_mm", 0.01)), step=0.01, format="%.3f",
                key="p3r")
            params["pipe3_K_minor"] = c4.number_input(
                "Fittings Resistance", min_value=0.0, max_value=20.0,
                value=float(defaults.get("pipe3_K_minor", 1.0)), step=0.5, format="%.1f",
                key="p3k")
        else:
            params["pipe3_diameter_in"] = 3.0
            params["pipe3_length_ft"] = 0.0
            params["pipe3_roughness_mm"] = 0.01
            params["pipe3_K_minor"] = 0.0

        # --- Pipe Segment 4 ---
        if num_pipes >= 4:
            st.subheader("Pipe Segment 4")
            c1, c2, c3, c4 = st.columns(4)
            params["pipe4_diameter_in"] = c1.number_input(
                "Pipe Diameter (in)", min_value=0.5, max_value=8.0,
                value=float(defaults.get("pipe4_diameter_in", 3.0)), step=0.5, format="%.1f",
                key="p4d")
            params["pipe4_length_ft"] = c2.number_input(
                "Hose Length (ft)", min_value=1.0, max_value=200.0,
                value=float(defaults.get("pipe4_length_ft", 25.0)), step=5.0, format="%.1f",
                key="p4l")
            params["pipe4_roughness_mm"] = c3.number_input(
                "Wall Roughness (mm)", min_value=0.001, max_value=1.0,
                value=float(defaults.get("pipe4_roughness_mm", 0.01)), step=0.01, format="%.3f",
                key="p4r")
            params["pipe4_K_minor"] = c4.number_input(
                "Fittings Resistance", min_value=0.0, max_value=20.0,
                value=float(defaults.get("pipe4_K_minor", 1.0)), step=0.5, format="%.1f",
                key="p4k")
        else:
            params["pipe4_diameter_in"] = 3.0
            params["pipe4_length_ft"] = 0.0
            params["pipe4_roughness_mm"] = 0.01
            params["pipe4_K_minor"] = 0.0

        # --- Pipe Segment 5 ---
        if num_pipes >= 5:
            st.subheader("Pipe Segment 5")
            c1, c2, c3, c4 = st.columns(4)
            params["pipe5_diameter_in"] = c1.number_input(
                "Pipe Diameter (in)", min_value=0.5, max_value=8.0,
                value=float(defaults.get("pipe5_diameter_in", 3.0)), step=0.5, format="%.1f",
                key="p5d")
            params["pipe5_length_ft"] = c2.number_input(
                "Hose Length (ft)", min_value=1.0, max_value=200.0,
                value=float(defaults.get("pipe5_length_ft", 25.0)), step=5.0, format="%.1f",
                key="p5l")
            params["pipe5_roughness_mm"] = c3.number_input(
                "Wall Roughness (mm)", min_value=0.001, max_value=1.0,
                value=float(defaults.get("pipe5_roughness_mm", 0.01)), step=0.01, format="%.3f",
                key="p5r")
            params["pipe5_K_minor"] = c4.number_input(
                "Fittings Resistance", min_value=0.0, max_value=20.0,
                value=float(defaults.get("pipe5_K_minor", 1.0)), step=0.5, format="%.1f",
                key="p5k")
        else:
            params["pipe5_diameter_in"] = 3.0
            params["pipe5_length_ft"] = 0.0
            params["pipe5_roughness_mm"] = 0.01
            params["pipe5_K_minor"] = 0.0

        st.info("""
        **How to calculate Fittings Resistance:** Add up the values for every fitting in your hose run:
        | Fitting | Resistance (K) | Example |
        |---------|---------------|---------|
        | Cam-lock coupling | 0.3 | Hose connection |
        | 90° elbow / bend | 0.9 | Sharp turn |
        | 45° elbow | 0.4 | Gentle turn |
        | Tee (branch) | 1.8 | T-junction |
        | Pipe entry | 0.5 | Where liquid enters pipe |
        | Pipe exit | 1.0 | Where liquid leaves pipe |
        
        *Example: 1 entry + 2 cam-locks + 1 elbow + 1 exit = 0.5 + 0.6 + 0.9 + 1.0 = **3.0***
        """)

    with tab_discharge:
        st.subheader("Where Is The Liquid Going?")
        st.caption("Describe the receiving tank or vessel.")
        c1, c2 = st.columns(2)
        params["elevation_change_ft"] = c1.number_input(
            "Height Difference (ft)", min_value=-20.0, max_value=50.0,
            value=float(defaults["elevation_change_ft"]), step=0.5, format="%.1f",
            help="How much higher (+) or lower (−) the receiver is compared to the truck outlet. 0 = same level. Pumping uphill requires more pressure.")
        params["receiver_pressure_psig"] = c2.number_input(
            "Receiver Tank Pressure (psig)", min_value=0.0, max_value=50.0,
            value=float(defaults["receiver_pressure_psig"]), step=0.5, format="%.1f",
            help="Pressure already inside the receiving tank. 0 = open to air (atmospheric). Higher pressure means harder to push liquid in.")

    with tab_sim:
        st.subheader("Simulation Settings")
        st.caption("Control how long and how detailed the simulation runs.")
        c1, c2, c3 = st.columns(3)
        params["stop_time_s"] = c1.number_input(
            "Max Run Time (seconds)", min_value=60, max_value=36000,
            value=int(defaults["stop_time_s"]), step=300,
            help="Maximum time to simulate. 3600 = 1 hour, 5400 = 1.5 hours. Simulation stops early if tank empties.")
        params["output_interval_s"] = c2.number_input(
            "Record Every (seconds)", min_value=0.1, max_value=10.0,
            value=float(defaults["output_interval_s"]), step=0.5, format="%.1f",
            help="How often to save a data point. 1 second gives detailed charts. 5 seconds = smaller file, coarser charts.")
        params["min_liquid_volume_gal"] = c3.number_input(
            "Stop When Below (gallons)", min_value=0, max_value=500,
            value=int(defaults["min_liquid_volume_gal"]), step=5,
            help="Simulation stops when liquid drops below this amount. Prevents pumping air. 10 gal is typical.")

    # ---- RUN BUTTON ----
    st.divider()

    # Show pressurization time summary with final SCFM value
    press_time_preview = calc_pressurization_time(
        params["tank_total_volume_gal"],
        params["initial_liquid_volume_gal"],
        params["initial_tank_pressure_psig"],
        params["air_supply_scfm"],
    )
    if press_time_preview > 0:
        headspace = max(params["tank_total_volume_gal"] - params["initial_liquid_volume_gal"], 0)
        st.info(
            f"⏱️ **Pre-pressurization:** {press_time_preview:.1f} min to reach "
            f"{params['initial_tank_pressure_psig']:.1f} psig at "
            f"{params['air_supply_scfm']:.0f} SCFM "
            f"(headspace: {headspace:.0f} gal). "
            f"This will be added to the valve-open transfer time for your **Total Realistic Time**."
        )

    # Validate
    warnings = []
    if params["initial_liquid_volume_gal"] > params["tank_total_volume_gal"]:
        warnings.append("Initial liquid volume exceeds tank capacity!")
    if params["relief_valve_pressure_psig"] <= params["max_tank_pressure_psig"]:
        warnings.append("Relief pressure should be above max operating pressure.")
    if params["pipe1_diameter_in"] != params["valve_diameter_in"]:
        warnings.append(f"Pipe 1 diameter ({params['pipe1_diameter_in']}″) differs from valve ({params['valve_diameter_in']}″).")

    for w in warnings:
        st.warning(w)

    col_run, col_status = st.columns([1, 3])
    with col_run:
        run_clicked = st.button("🚀 Run Simulation", type="primary", use_container_width=True)

    if run_clicked:
        # Sanitize name
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', run_name.strip())[:50]
        if not safe_name:
            safe_name = "custom_run"

        # Generate YAML
        yaml_content = generate_yaml_config(params, safe_name)
        config_filename = f"config/app_{safe_name}.yaml"
        config_path = os.path.join("/work", config_filename)

        with open(config_path, "w") as f:
            f.write(yaml_content)

        with col_status:
            st.info(f"Config written: {config_filename}")

        # Run simulation
        with st.status("Running simulation...", expanded=True) as status:
            st.write("📝 Generating YAML config...")
            st.code(yaml_content[:500] + "...", language="yaml")

            st.write("⚙️ Starting OpenModelica solver...")
            start_time = time.time()
            success, output = run_simulation(config_filename)
            elapsed = time.time() - start_time

            if success:
                status.update(label=f"Simulation complete ({elapsed:.1f}s)", state="complete")
                st.write("✅ Simulation finished successfully!")

                # Find the output
                run_dir = find_latest_run(safe_name)
                if run_dir:
                    csv_path = os.path.join(run_dir, "outputs.csv")
                    if os.path.isfile(csv_path):
                        st.session_state["latest_run_csv"] = csv_path
                        st.session_state["latest_run_name"] = safe_name
                    else:
                        st.warning("Results CSV not found in run directory.")
                else:
                    st.warning("Run directory not found after simulation.")

                # Show raw output in expander
                with st.expander("Simulation Log", expanded=False):
                    st.code(output, language="text")
            else:
                status.update(label="Simulation FAILED", state="error")
                st.error("Simulation failed!")
                st.code(output, language="text")

    # ---- SHOW RESULTS ----
    if "latest_run_csv" in st.session_state:
        st.divider()
        st.subheader(f"Results: {st.session_state.get('latest_run_name', 'Latest')}")

        df = load_csv(st.session_state["latest_run_csv"])

        # Summary metrics (computed on full data)
        summary = compute_summary(df)

        # Trim data to meaningful window for charts
        df_plot = trim_to_completion(df)

        # Calculate & inject pressurization time if starting pressure > 0
        press_time_min = calc_pressurization_time(
            params["tank_total_volume_gal"],
            params["initial_liquid_volume_gal"],
            params["initial_tank_pressure_psig"],
            params["air_supply_scfm"],
        )
        if press_time_min > 0:
            # Extract numeric transfer time from summary
            transfer_str = summary.get("Transfer Time (min)", "0")
            transfer_val = float(re.sub(r'[^0-9.]', '', transfer_str.split()[0]))
            total_real = press_time_min + transfer_val
            summary["Pressurize Time (min)"] = f"{press_time_min:.1f}"
            summary["Total Realistic Time (min)"] = f"{total_real:.1f}"

        cols = st.columns(len(summary))
        for i, (label, value) in enumerate(summary.items()):
            cols[i].metric(label, value)

        # Charts (use trimmed data)
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(build_pressure_chart(df_plot), use_container_width=True)
        with c2:
            st.plotly_chart(build_flow_chart(df_plot), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(build_volume_remaining_chart(df_plot), use_container_width=True)
        with c2:
            st.plotly_chart(build_volume_transferred_chart(df_plot), use_container_width=True)

        # Engineering detail in expander
        with st.expander("Engineering Detail", expanded=False):
            eng_charts = build_engineering_charts(df_plot)
            for chart in eng_charts:
                st.plotly_chart(chart, use_container_width=True)

        # Download section
        st.divider()
        st.subheader("📥 Export")
        run_name = st.session_state.get("latest_run_name", "simulation")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            csv_data = df.to_csv(index=False)
            st.download_button(
                "📥 Download CSV Data",
                csv_data,
                f"{run_name}_results.csv",
                "text/csv",
                use_container_width=True,
            )
        with dl_col2:
            if st.button("📄 Generate PDF Report", type="primary", use_container_width=True, key="pdf_run"):
                with st.spinner("Generating PDF report..."):
                    try:
                        pdf_bytes = generate_pdf_report(
                            df=df,
                            scenario=run_name,
                            summary=summary,
                            params=params,
                        )
                        st.session_state["pdf_report"] = pdf_bytes
                        st.session_state["pdf_report_name"] = run_name
                    except Exception as e:
                        st.error(f"PDF generation failed: {e}")

        if "pdf_report" in st.session_state:
            st.download_button(
                "⬇️ Download PDF Report",
                st.session_state["pdf_report"],
                f"{st.session_state.get('pdf_report_name', 'report')}_report.pdf",
                "application/pdf",
                use_container_width=True,
            )


# =============================================================================
# PAGE: PAST RESULTS
# =============================================================================


def page_past_results():
    st.header("Past Results")

    runs = discover_runs(DATA_DIR)
    if not runs:
        st.info("No simulation results found. Run a simulation first!")
        return

    # Selection
    run_options = {r["name"]: r for r in runs}
    selected_names = st.multiselect(
        "Select runs to view",
        list(run_options.keys()),
        default=[runs[-1]["name"]] if runs else [],
    )

    if not selected_names:
        st.info("Select one or more runs above.")
        return

    for name in selected_names:
        run = run_options[name]
        df = load_csv(run["csv_path"])
        df_plot = trim_to_completion(df)

        st.subheader(f"📊 {run['scenario']}")

        # Summary
        summary = compute_summary(df)
        cols = st.columns(min(len(summary), 6))
        for i, (label, value) in enumerate(summary.items()):
            cols[i % len(cols)].metric(label, value)

        # Charts (use trimmed data)
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(build_pressure_chart(df_plot, run["scenario"]),
                          use_container_width=True, key=f"p_{name}")
        with c2:
            st.plotly_chart(build_flow_chart(df_plot, run["scenario"]),
                          use_container_width=True, key=f"f_{name}")

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(build_volume_remaining_chart(df_plot, run["scenario"]),
                          use_container_width=True, key=f"vr_{name}")
        with c2:
            st.plotly_chart(build_volume_transferred_chart(df_plot, run["scenario"]),
                          use_container_width=True, key=f"vt_{name}")

        with st.expander("Engineering Detail"):
            eng_charts = build_engineering_charts(df_plot, run["scenario"])
            for j, chart in enumerate(eng_charts):
                st.plotly_chart(chart, use_container_width=True, key=f"eng_{name}_{j}")

        # PDF export for past results
        pdf_key = f"pdf_past_{name}"
        if st.button("📄 Generate PDF Report", key=f"btn_pdf_{name}", use_container_width=False):
            with st.spinner("Generating PDF report..."):
                try:
                    past_summary = compute_summary(df)
                    pdf_bytes = generate_pdf_report(
                        df=df_plot,
                        scenario=run["scenario"],
                        summary=past_summary,
                        params=run.get("metadata", {}).get("config", {}),
                    )
                    st.session_state[pdf_key] = pdf_bytes
                except Exception as e:
                    st.error(f"PDF generation failed: {e}")

        if pdf_key in st.session_state:
            st.download_button(
                "⬇️ Download PDF Report",
                st.session_state[pdf_key],
                f"{run['scenario']}_report.pdf",
                "application/pdf",
                key=f"dl_pdf_{name}",
            )

        # Metadata
        if run["metadata"]:
            with st.expander("Run Metadata"):
                st.json(run["metadata"])

        st.divider()

    # ---- Comparison overlay ----
    if len(selected_names) > 1:
        st.subheader("📈 Comparison Overlay")

        for metric, col_name, ylabel, title in [
            ("Pressure", "P_tank_psig", "psig", "Tank Pressure Comparison"),
            ("Flow", None, "GPM", "Flow Rate Comparison"),
            ("Remaining", "V_liquid_gal", "gal", "Volume Remaining Comparison"),
        ]:
            fig = go.Figure()
            for i, name in enumerate(selected_names):
                run = run_options[name]
                cmp_df = trim_to_completion(load_csv(run["csv_path"]))
                if metric == "Flow":
                    y_col = "Q_total_gpm" if "Q_total_gpm" in cmp_df.columns else "Q_L_gpm"
                else:
                    y_col = col_name
                if y_col in cmp_df.columns:
                    fig.add_trace(go.Scatter(
                        x=cmp_df["time_min"], y=cmp_df[y_col],
                        mode="lines", name=run["scenario"],
                    ))
            fig.update_layout(title=title, xaxis_title="Time (min)",
                yaxis_title=ylabel, template="plotly_white", height=400)
            st.plotly_chart(fig, use_container_width=True, key=f"cmp_{metric}")


# =============================================================================
# PAGE: SYSTEM INFO
# =============================================================================


def page_system_info():
    st.header("System Information")

    st.subheader("System Schematic")
    st.code("""
         Compressed Air In
              │ ṁ_air_in
              ▼
    ┌─────────────────────────────┐
    │      ULLAGE GAS (ideal)     │  P_tank, V_gas, T_gas
    │      m_gas, isothermal      │
    ├ ─ ─ ─ ─ ─ liquid level  ─ ─┤  h_liquid
    │      LIQUID (incompress.)   │  V_liquid, ρ_L, μ_L
    │      DOT-407 horiz. cyl.    │
    └──────────────┬──────────────┘
                   │              ┌── Relief Valve ──► Atm
                   ▼              │
    ┌──────────────┴──────────────┐
    │  OUTLET VALVE (K model)     │
    └──────────────┬──────────────┘
                   │  Q_L
                   ▼
    ┌─────────────────────────────┐
    │  PIPE SEGMENT 1             │  (always active)
    └──────────────┬──────────────┘
                   ▼
    ┌─────────────────────────────┐
    │  PIPE SEGMENT 2 … 5        │  (optional — L=0 means inactive)
    └──────────────┬──────────────┘
                   ▼  + Δz
    ┌─────────────────────────────┐
    │  RECEIVER (P_receiver)      │
    └─────────────────────────────┘
    """, language="text")

    st.subheader("Model Details")
    st.markdown("""
    - **Solver:** DASSL (DAE system)
    - **States:** Gas mass ($m_{gas}$), Liquid volume ($V_{liquid}$)
    - **Pipe segments:** Up to 5 in series (unused segments have L=0, contributing zero pressure drop)
    - **Friction:** Smooth laminar↔turbulent blend (Swamee-Jain + cubic smoothstep)
    - **Gas model:** Ideal gas, isothermal
    - **Geometry:** Horizontal cylinder with algebraic level solve
    """)

    st.subheader("Available Runs")
    runs = discover_runs(DATA_DIR)
    if runs:
        data = []
        for r in runs:
            data.append({
                "Name": r["name"],
                "Scenario": r["scenario"],
                "Timestamp": r["timestamp"][:19] if r["timestamp"] else "—",
                "Status": r["metadata"].get("status", "—"),
            })
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    else:
        st.info("No runs found.")

    # --- Logo Upload ---
    st.subheader("Company Logo")
    logo_dir = Path("/work/data/assets")
    logo_dir.mkdir(exist_ok=True)
    current_logo = logo_dir / "logo.png"
    if current_logo.exists():
        st.image(str(current_logo), width=200, caption="Current logo")
    else:
        for ext in ("jpg", "jpeg", "svg", "webp"):
            alt = (logo_dir / "logo").with_suffix(f".{ext}")
            if alt.exists():
                st.image(str(alt), width=200, caption="Current logo")
                current_logo = alt
                break
        else:
            st.info("No logo uploaded yet.")
    uploaded = st.file_uploader(
        "Upload company logo (PNG, JPG, SVG)",
        type=["png", "jpg", "jpeg", "svg", "webp"],
        key="logo_upload",
    )
    if uploaded is not None:
        # Determine extension from uploaded file
        ext = Path(uploaded.name).suffix.lower() or ".png"
        save_path = logo_dir / f"logo{ext}"
        save_path.write_bytes(uploaded.getvalue())
        # Remove other logo files to avoid confusion
        for old in logo_dir.glob("logo.*"):
            if old != save_path:
                old.unlink()
        st.success(f"Logo saved! Refresh the page to see it in the sidebar.")
        st.image(uploaded, width=200, caption="New logo")


# =============================================================================
# MAIN APP
# =============================================================================


def main():
    st.set_page_config(
        page_title="TankerTransfer V2",
        page_icon="🛢️",
        layout="wide",
    )

    # --- Company Logo ---
    logo_dir = Path("/work/data/assets")
    logo_path = logo_dir / "logo.png"
    if not logo_path.exists():
        # Also check common alternative extensions
        for ext in ("jpg", "jpeg", "svg", "webp"):
            alt = logo_path.with_suffix(f".{ext}")
            if alt.exists():
                logo_path = alt
                break
    if logo_path.exists():
        logo_bytes = logo_path.read_bytes()
        encoded = base64.b64encode(logo_bytes).decode()
        mime = "image/png"
        if logo_path.suffix in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        elif logo_path.suffix == ".svg":
            mime = "image/svg+xml"
        elif logo_path.suffix == ".webp":
            mime = "image/webp"
        st.sidebar.markdown(
            f'<div style="text-align:center;padding:8px 0 4px 0;">'
            f'<img src="data:{mime};base64,{encoded}" '
            f'style="max-width:85%;height:auto;border-radius:6px;">'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.sidebar.title("🛢️ TankerTransfer V2")
    st.sidebar.markdown("Air-Displacement Tanker Unloading Simulator")

    page = st.sidebar.radio(
        "Navigation",
        ["🚀 Run Simulation", "📊 Past Results", "ℹ️ System Info"],
    )

    # Health check endpoint
    query_params = st.query_params
    if query_params.get("healthz"):
        st.write("ok")
        return

    if page == "🚀 Run Simulation":
        page_run_simulation()
    elif page == "📊 Past Results":
        page_past_results()
    elif page == "ℹ️ System Info":
        page_system_info()


if __name__ == "__main__":
    main()
