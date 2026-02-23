"""
TankerTransfer — Interactive Visualization Dashboard
=====================================================

Streamlit + Plotly web dashboard for exploring simulation results.

Usage (via Docker Compose):
    docker compose up -d visual-dashboard
    # Then SSH tunnel: ssh -L 8501:localhost:8501 user@vps
    # Open: http://localhost:8501

Direct (for development):
    streamlit run python/dashboard.py --server.headless=true
"""

import os
import json
import glob

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# =============================================================================
# CONFIGURATION
# =============================================================================

DATA_DIR = os.environ.get("DASHBOARD_DATA_DIR", "/work/data/runs")

# Chart color scheme
COLORS = {
    "pressure": "#EF553B",   # Red
    "flow": "#636EFA",       # Blue
    "remaining": "#00CC96",  # Green
    "transferred": "#AB63FA", # Purple
}

# =============================================================================
# DATA DISCOVERY
# =============================================================================


def discover_runs(data_dir: str) -> list[dict]:
    """Scan data_dir for simulation run directories containing outputs.csv."""
    runs = []
    pattern = os.path.join(data_dir, "*", "outputs.csv")
    for csv_path in sorted(glob.glob(pattern)):
        run_dir = os.path.dirname(csv_path)
        run_name = os.path.basename(run_dir)

        # Try to load run_log.json for metadata
        log_path = os.path.join(run_dir, "run_log.json")
        metadata = {}
        if os.path.isfile(log_path):
            try:
                with open(log_path) as f:
                    metadata = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        scenario = metadata.get("scenario", run_name)
        timestamp = metadata.get("timestamp", "")

        runs.append({
            "name": run_name,
            "scenario": scenario,
            "timestamp": timestamp,
            "csv_path": csv_path,
            "run_dir": run_dir,
            "metadata": metadata,
        })

    return runs


def load_csv(csv_path: str) -> pd.DataFrame:
    """Load simulation CSV and add time_min column."""
    df = pd.read_csv(csv_path)
    if "time" in df.columns:
        df["time_min"] = df["time"] / 60.0
    return df


# =============================================================================
# CHART BUILDERS
# =============================================================================


def build_pressure_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    """Tank pressure vs time."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"],
        y=df["P_tank_psig"],
        mode="lines",
        name="P_tank",
        line=dict(color=COLORS["pressure"], width=2),
        hovertemplate="Time: %{x:.1f} min<br>Pressure: %{y:.2f} psig<extra></extra>",
    ))
    fig.update_layout(
        title=f"Tank Pressure — {scenario}",
        xaxis_title="Time (min)",
        yaxis_title="Pressure (psig)",
        hovermode="x unified",
        template="plotly_white",
        height=400,
    )
    return fig


def build_flow_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    """Flow rate vs time."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"],
        y=df["Q_total_gpm"],
        mode="lines",
        name="Q_total",
        line=dict(color=COLORS["flow"], width=2),
        hovertemplate="Time: %{x:.1f} min<br>Flow: %{y:.2f} GPM<extra></extra>",
    ))

    # Add individual components if available
    if "Q_pressure" in df.columns:
        # Convert m³/s to GPM for sub-components
        gpm_factor = 264.172 * 60.0
        fig.add_trace(go.Scatter(
            x=df["time_min"],
            y=df["Q_pressure"] * gpm_factor,
            mode="lines",
            name="Q_pressure",
            line=dict(color=COLORS["pressure"], width=1, dash="dash"),
            hovertemplate="Time: %{x:.1f} min<br>Pressure Flow: %{y:.2f} GPM<extra></extra>",
        ))
    if "Q_pump_flow" in df.columns:
        gpm_factor = 264.172 * 60.0
        fig.add_trace(go.Scatter(
            x=df["time_min"],
            y=df["Q_pump_flow"] * gpm_factor,
            mode="lines",
            name="Q_pump",
            line=dict(color=COLORS["transferred"], width=1, dash="dash"),
            hovertemplate="Time: %{x:.1f} min<br>Pump Flow: %{y:.2f} GPM<extra></extra>",
        ))

    fig.update_layout(
        title=f"Flow Rate — {scenario}",
        xaxis_title="Time (min)",
        yaxis_title="Flow Rate (GPM)",
        hovermode="x unified",
        template="plotly_white",
        height=400,
    )
    return fig


def build_volume_remaining_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    """Volume remaining vs time."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"],
        y=df["V_liquid_gal"],
        mode="lines",
        name="V_remaining",
        line=dict(color=COLORS["remaining"], width=2),
        fill="tozeroy",
        fillcolor="rgba(0, 204, 150, 0.1)",
        hovertemplate="Time: %{x:.1f} min<br>Remaining: %{y:.0f} gal<extra></extra>",
    ))
    fig.update_layout(
        title=f"Volume Remaining — {scenario}",
        xaxis_title="Time (min)",
        yaxis_title="Volume (gal)",
        hovermode="x unified",
        template="plotly_white",
        height=400,
    )
    return fig


def build_transferred_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    """Transferred volume vs time."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"],
        y=df["V_transferred_gal"],
        mode="lines",
        name="V_transferred",
        line=dict(color=COLORS["transferred"], width=2),
        fill="tozeroy",
        fillcolor="rgba(171, 99, 250, 0.1)",
        hovertemplate="Time: %{x:.1f} min<br>Transferred: %{y:.0f} gal<extra></extra>",
    ))
    fig.update_layout(
        title=f"Cumulative Transferred — {scenario}",
        xaxis_title="Time (min)",
        yaxis_title="Volume (gal)",
        hovermode="x unified",
        template="plotly_white",
        height=400,
    )
    return fig


def build_flow_diagram(df: pd.DataFrame, time_idx: int, scenario: str) -> go.Figure:
    """
    Build an interactive system flow diagram showing the physical layout:
    Air Supply → Tank (ullage + liquid) → Hose → Receiver
    with live values from the simulation at the given time index.
    """
    row = df.iloc[time_idx]
    t_min = row.get("time_min", row.get("time", 0) / 60.0)
    p_psig = row.get("P_tank_psig", 0)
    q_gpm = row.get("Q_total_gpm", 0)
    v_liq_gal = row.get("V_liquid_gal", 0)
    v_trans_gal = row.get("V_transferred_gal", 0)
    v_hose_val = row.get("v_hose", 0)
    re_val = row.get("Re", 0)

    # Estimate fill level (fraction) for visual
    max_liq = df["V_liquid_gal"].max()
    fill_frac = v_liq_gal / max_liq if max_liq > 0 else 0

    fig = go.Figure()

    # --- Canvas setup ---
    fig.update_xaxes(range=[-0.5, 10.5], visible=False, fixedrange=True)
    fig.update_yaxes(range=[-1.5, 7.5], visible=False, fixedrange=True,
                     scaleanchor="x", scaleratio=1)

    # ===================== AIR SUPPLY (top-left) =====================
    # Compressor icon (box)
    fig.add_shape(type="rect", x0=0.5, y0=5.8, x1=2.5, y1=7.0,
                  fillcolor="#E3F2FD", line=dict(color="#1565C0", width=2))
    fig.add_annotation(x=1.5, y=6.4, text="<b>🌬️ Air Supply</b>",
                       showarrow=False, font=dict(size=12, color="#1565C0"))
    fig.add_annotation(x=1.5, y=6.0, text=f"19 SCFM",
                       showarrow=False, font=dict(size=10, color="#666"))

    # Arrow: air → tank
    fig.add_annotation(x=1.5, y=5.3, ax=1.5, ay=5.7,
                       arrowhead=3, arrowsize=1.5, arrowwidth=2,
                       arrowcolor="#1565C0", showarrow=True, text="")
    fig.add_annotation(x=1.5, y=5.5, text="ṁ_air",
                       showarrow=False, font=dict(size=9, color="#1565C0"))

    # ===================== TANKER (center) =====================
    # Tank outer shell
    tank_x0, tank_x1 = 0.0, 3.0
    tank_y0, tank_y1 = 1.5, 5.2

    fig.add_shape(type="rect", x0=tank_x0, y0=tank_y0, x1=tank_x1, y1=tank_y1,
                  fillcolor="#FFF8E1", line=dict(color="#F57F17", width=3))

    # Liquid fill (bottom portion of tank)
    liq_top = tank_y0 + fill_frac * (tank_y1 - tank_y0)
    if fill_frac > 0.001:
        fig.add_shape(type="rect",
                      x0=tank_x0 + 0.05, y0=tank_y0 + 0.05,
                      x1=tank_x1 - 0.05, y1=liq_top,
                      fillcolor="rgba(255, 152, 0, 0.5)",
                      line=dict(color="#E65100", width=1))

    # Liquid surface line
    if 0.01 < fill_frac < 0.99:
        fig.add_shape(type="line",
                      x0=tank_x0 + 0.05, y0=liq_top,
                      x1=tank_x1 - 0.05, y1=liq_top,
                      line=dict(color="#E65100", width=2, dash="dash"))

    # Ullage label (upper portion)
    ullage_y = (liq_top + tank_y1) / 2 if fill_frac < 0.9 else tank_y1 - 0.2
    fig.add_annotation(x=1.5, y=min(ullage_y, tank_y1 - 0.15),
                       text=f"<b>Ullage Gas</b><br>{p_psig:.1f} psig",
                       showarrow=False,
                       font=dict(size=11, color="#D84315"))

    # Liquid label (lower portion)
    liq_label_y = (tank_y0 + liq_top) / 2 if fill_frac > 0.15 else tank_y0 + 0.3
    if fill_frac > 0.05:
        fig.add_annotation(x=1.5, y=liq_label_y,
                           text=f"<b>Oil</b><br>{v_liq_gal:.0f} gal",
                           showarrow=False,
                           font=dict(size=11, color="#4E342E"))

    # Tank label
    fig.add_annotation(x=1.5, y=tank_y0 - 0.3,
                       text="<b>🛢️ TANKER</b>",
                       showarrow=False, font=dict(size=13, color="#F57F17"))

    # ===================== HOSE (center-right) =====================
    # Horizontal pipe from tank to receiver
    hose_y = 2.0
    hose_x0 = tank_x1
    hose_x1 = 7.0

    # Pipe body
    fig.add_shape(type="rect",
                  x0=hose_x0, y0=hose_y - 0.2,
                  x1=hose_x1, y1=hose_y + 0.2,
                  fillcolor="#E0E0E0" if q_gpm < 0.1 else "#BBDEFB",
                  line=dict(color="#616161", width=2))

    # Flow direction arrows inside pipe
    if q_gpm > 0.1:
        for ax_pos in [3.8, 4.8, 5.8]:
            fig.add_annotation(x=ax_pos + 0.4, y=hose_y,
                               ax=ax_pos, ay=hose_y,
                               arrowhead=2, arrowsize=1, arrowwidth=2,
                               arrowcolor="#1565C0", showarrow=True, text="")

    # Hose labels
    fig.add_annotation(x=5.0, y=hose_y + 0.55,
                       text=f"<b>Hose</b>  {q_gpm:.1f} GPM",
                       showarrow=False,
                       font=dict(size=11,
                                 color="#1565C0" if q_gpm > 0.1 else "#9E9E9E"))
    fig.add_annotation(x=5.0, y=hose_y - 0.5,
                       text=f"v={v_hose_val:.3f} m/s  Re={re_val:.0f}",
                       showarrow=False, font=dict(size=9, color="#888"))

    # ===================== AODD PUMP (optional, below hose) =====================
    # Show pump info if pump flow > 0
    q_pump = row.get("Q_pump_flow", 0)
    gpm_factor = 264.172 * 60.0
    q_pump_gpm = q_pump * gpm_factor if q_pump else 0

    if q_pump_gpm > 0.01:
        fig.add_shape(type="rect", x0=4.0, y0=0.0, x1=6.0, y1=0.9,
                      fillcolor="#F3E5F5", line=dict(color="#7B1FA2", width=2))
        fig.add_annotation(x=5.0, y=0.45,
                           text=f"<b>⚙️ AODD Pump</b><br>{q_pump_gpm:.1f} GPM",
                           showarrow=False,
                           font=dict(size=10, color="#7B1FA2"))
        # Arrow from pump into hose
        fig.add_annotation(x=5.0, y=hose_y - 0.25, ax=5.0, ay=0.95,
                           arrowhead=3, arrowsize=1.2, arrowwidth=2,
                           arrowcolor="#7B1FA2", showarrow=True, text="")

    # ===================== RECEIVER (right) =====================
    fig.add_shape(type="rect", x0=7.0, y0=1.2, x1=9.5, y1=3.5,
                  fillcolor="#E8F5E9", line=dict(color="#2E7D32", width=2))

    # Fill level in receiver
    recv_fill = v_trans_gal / max_liq if max_liq > 0 else 0
    recv_top = 1.25 + recv_fill * (3.45 - 1.25)
    if recv_fill > 0.005:
        fig.add_shape(type="rect",
                      x0=7.05, y0=1.25, x1=9.45, y1=min(recv_top, 3.45),
                      fillcolor="rgba(76, 175, 80, 0.4)",
                      line=dict(color="#1B5E20", width=1))

    fig.add_annotation(x=8.25, y=2.7,
                       text=f"<b>Received</b><br>{v_trans_gal:.0f} gal",
                       showarrow=False,
                       font=dict(size=11, color="#1B5E20"))
    fig.add_annotation(x=8.25, y=1.0,
                       text="<b>📦 RECEIVER</b>",
                       showarrow=False, font=dict(size=13, color="#2E7D32"))

    # ===================== TIME BADGE =====================
    fig.add_annotation(x=9.5, y=7.0,
                       text=f"<b>t = {t_min:.1f} min</b>",
                       showarrow=False,
                       font=dict(size=14, color="#333"),
                       bgcolor="#FFF9C4", bordercolor="#F9A825",
                       borderwidth=2, borderpad=6)

    # ===================== LAYOUT =====================
    fig.update_layout(
        title=f"System Flow Diagram — {scenario}",
        width=900, height=550,
        template="plotly_white",
        showlegend=False,
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="white",
    )

    return fig


def build_comparison_chart(runs_data: list[tuple[str, pd.DataFrame]]) -> go.Figure:
    """4-panel comparison of all selected scenarios."""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Tank Pressure (psig)",
            "Flow Rate (GPM)",
            "Volume Remaining (gal)",
            "Transferred Volume (gal)",
        ),
        horizontal_spacing=0.08,
        vertical_spacing=0.12,
    )

    colors = ["#EF553B", "#636EFA", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3"]

    for i, (name, df) in enumerate(runs_data):
        color = colors[i % len(colors)]
        show_legend = True

        fig.add_trace(go.Scatter(
            x=df["time_min"], y=df["P_tank_psig"],
            mode="lines", name=name, legendgroup=name,
            showlegend=show_legend,
            line=dict(color=color, width=2),
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df["time_min"], y=df["Q_total_gpm"],
            mode="lines", name=name, legendgroup=name,
            showlegend=False,
            line=dict(color=color, width=2),
        ), row=1, col=2)

        fig.add_trace(go.Scatter(
            x=df["time_min"], y=df["V_liquid_gal"],
            mode="lines", name=name, legendgroup=name,
            showlegend=False,
            line=dict(color=color, width=2),
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=df["time_min"], y=df["V_transferred_gal"],
            mode="lines", name=name, legendgroup=name,
            showlegend=False,
            line=dict(color=color, width=2),
        ), row=2, col=2)

    fig.update_layout(
        title="Scenario Comparison",
        hovermode="x unified",
        template="plotly_white",
        height=700,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
    )

    # Axis labels
    fig.update_xaxes(title_text="Time (min)", row=2, col=1)
    fig.update_xaxes(title_text="Time (min)", row=2, col=2)
    fig.update_yaxes(title_text="psig", row=1, col=1)
    fig.update_yaxes(title_text="GPM", row=1, col=2)
    fig.update_yaxes(title_text="gal", row=2, col=1)
    fig.update_yaxes(title_text="gal", row=2, col=2)

    return fig


# =============================================================================
# STREAMLIT APP
# =============================================================================


def main():
    st.set_page_config(
        page_title="TankerTransfer Dashboard",
        page_icon="🛢️",
        layout="wide",
    )

    st.title("🛢️ TankerTransfer — Simulation Dashboard")
    st.caption("Interactive visualization of truck tanker liquid transfer simulations")

    # --- Discover available runs ---
    runs = discover_runs(DATA_DIR)

    if not runs:
        st.warning(
            f"No simulation outputs found in `{DATA_DIR}`.\n\n"
            "Run simulations first:\n"
            "```bash\n"
            "cd /opt/sim-lab/truck-tanker-sim-env\n"
            "./scripts/run_app.sh\n"
            "```"
        )
        return

    # --- Sidebar: Scenario Selection ---
    st.sidebar.header("📋 Scenario Selection")

    run_options = {r["name"]: r for r in runs}
    selected_names = st.sidebar.multiselect(
        "Select simulation run(s):",
        options=list(run_options.keys()),
        default=[runs[0]["name"]] if runs else [],
        help="Select one or more runs to visualize",
    )

    if not selected_names:
        st.info("Select at least one simulation run from the sidebar.")
        return

    selected_runs = [run_options[n] for n in selected_names]

    # --- Sidebar: View mode ---
    st.sidebar.header("📊 View Mode")
    view_mode = st.sidebar.radio(
        "Display mode:",
        options=["Individual Charts", "Comparison Overlay", "System Flow Diagram"],
        index=0,
        help="Individual: detailed per-scenario | Comparison: overlay all | Flow: animated system schematic",
    )

    # --- Load data ---
    runs_data = []
    for run_info in selected_runs:
        try:
            df = load_csv(run_info["csv_path"])
            runs_data.append((run_info["scenario"], df, run_info))
        except Exception as e:
            st.error(f"Failed to load {run_info['name']}: {e}")

    if not runs_data:
        st.error("No data could be loaded.")
        return

    # --- Comparison mode ---
    if view_mode == "Comparison Overlay" and len(runs_data) >= 1:
        st.header("Scenario Comparison")
        comparison_data = [(name, df) for name, df, _ in runs_data]
        fig = build_comparison_chart(comparison_data)
        st.plotly_chart(fig, use_container_width=True)

        # Summary table
        st.subheader("Summary Statistics")
        summary_rows = []
        for name, df, info in runs_data:
            summary_rows.append({
                "Scenario": name,
                "Peak Pressure (psig)": f"{df['P_tank_psig'].max():.2f}",
                "Peak Flow (GPM)": f"{df['Q_total_gpm'].max():.2f}",
                "Transferred (gal)": f"{df['V_transferred_gal'].iloc[-1]:.0f}",
                "Remaining (gal)": f"{df['V_liquid_gal'].iloc[-1]:.0f}",
                "Sim Time (min)": f"{df['time'].iloc[-1] / 60:.1f}",
            })
        st.table(pd.DataFrame(summary_rows))

    # --- System Flow Diagram mode ---
    elif view_mode == "System Flow Diagram":
        for scenario_name, df, run_info in runs_data:
            st.header(f"🔧 System Flow — {scenario_name}")
            st.caption("Drag the time slider to see how the system evolves")

            # Time slider
            max_idx = len(df) - 1
            # Default to a point where things are interesting (~10% through)
            default_idx = min(max_idx // 10, max_idx)

            time_idx = st.slider(
                f"Time step ({scenario_name})",
                min_value=0,
                max_value=max_idx,
                value=default_idx,
                format=f"Step %d / {max_idx}",
                key=f"flow_slider_{scenario_name}",
            )

            # Show current time
            row = df.iloc[time_idx]
            t_sec = row.get("time", 0)
            st.write(f"**Time:** {t_sec:.0f} s ({t_sec/60:.1f} min)")

            # Render diagram
            fig = build_flow_diagram(df, time_idx, scenario_name)
            st.plotly_chart(fig, use_container_width=True)

            # Quick stats for this timestep
            scol1, scol2, scol3, scol4, scol5 = st.columns(5)
            scol1.metric("Pressure", f"{row.get('P_tank_psig', 0):.1f} psig")
            scol2.metric("Flow", f"{row.get('Q_total_gpm', 0):.1f} GPM")
            scol3.metric("Remaining", f"{row.get('V_liquid_gal', 0):.0f} gal")
            scol4.metric("Transferred", f"{row.get('V_transferred_gal', 0):.0f} gal")
            scol5.metric("Hose Velocity", f"{row.get('v_hose', 0):.3f} m/s")

            st.divider()

    # --- Individual mode ---
    elif view_mode == "Individual Charts":
        for scenario_name, df, run_info in runs_data:
            st.header(f"📈 {scenario_name}")

            # Metadata expander
            meta = run_info.get("metadata", {})
            if meta:
                with st.expander("Run Metadata", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Timestamp:** {meta.get('timestamp', 'N/A')}")
                        st.write(f"**Config:** {meta.get('config_file', 'N/A')}")
                        st.write(f"**Status:** {meta.get('status', 'N/A')}")
                    with col2:
                        outputs = meta.get("outputs", {})
                        st.write(f"**Output rows:** {outputs.get('output_rows', 'N/A')}")
                        st.write(f"**CSV:** {outputs.get('csv', 'N/A')}")

            # Stats row
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Peak Pressure", f"{df['P_tank_psig'].max():.1f} psig")
            col2.metric("Peak Flow", f"{df['Q_total_gpm'].max():.1f} GPM")
            col3.metric("Transferred", f"{df['V_transferred_gal'].iloc[-1]:.0f} gal")
            col4.metric("Remaining", f"{df['V_liquid_gal'].iloc[-1]:.0f} gal")

            # Charts - 2x2 grid
            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                st.plotly_chart(
                    build_pressure_chart(df, scenario_name),
                    use_container_width=True,
                )
                st.plotly_chart(
                    build_volume_remaining_chart(df, scenario_name),
                    use_container_width=True,
                )
            with chart_col2:
                st.plotly_chart(
                    build_flow_chart(df, scenario_name),
                    use_container_width=True,
                )
                st.plotly_chart(
                    build_transferred_chart(df, scenario_name),
                    use_container_width=True,
                )

            st.divider()

    # --- Sidebar: Data info ---
    st.sidebar.header("ℹ️ Data Info")
    st.sidebar.write(f"**Data directory:** `{DATA_DIR}`")
    st.sidebar.write(f"**Runs found:** {len(runs)}")
    for run_info in runs:
        st.sidebar.write(f"- {run_info['scenario']}")


if __name__ == "__main__":
    main()
