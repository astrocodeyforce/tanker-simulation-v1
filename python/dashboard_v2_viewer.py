"""
TankerTransfer V2 — Interactive Visualization Dashboard
========================================================

Streamlit + Plotly web dashboard for exploring simulation results.
Supports both V1 and V2 output formats.

Usage (via Docker Compose):
    docker compose up -d visual-dashboard
    # SSH tunnel: ssh -L 8501:localhost:8501 user@vps
    # Open: http://localhost:8501
"""

import os
import json
import glob
import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# =============================================================================
# CONFIGURATION
# =============================================================================

DATA_DIR = os.environ.get("DASHBOARD_DATA_DIR", "/work/data/runs")

COLORS = {
    "pressure": "#EF553B",
    "flow": "#636EFA",
    "remaining": "#00CC96",
    "transferred": "#AB63FA",
    "head": "#FFA15A",
    "valve": "#FF6692",
    "seg1": "#19D3F3",
    "seg2": "#B6E880",
}

PSI_CONV = 6894.76  # Pa per psi

# =============================================================================
# DATA DISCOVERY
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
    """Load simulation CSV and normalize column names for V1/V2 compat."""
    df = pd.read_csv(csv_path)
    if "time" in df.columns:
        df["time_min"] = df["time"] / 60.0

    # V2 compatibility: map new names to common names used in charts
    if "Q_L_gpm" in df.columns and "Q_total_gpm" not in df.columns:
        df["Q_total_gpm"] = df["Q_L_gpm"]
    if "Q_L" in df.columns and "Q_total" not in df.columns:
        df["Q_total"] = df["Q_L"]
    return df


# =============================================================================
# CHART BUILDERS
# =============================================================================


def build_pressure_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"], y=df["P_tank_psig"],
        mode="lines", name="P_tank",
        line=dict(color=COLORS["pressure"], width=2),
        hovertemplate="Time: %{x:.1f} min<br>Pressure: %{y:.2f} psig<extra></extra>",
    ))
    fig.update_layout(
        title=f"Tank Pressure — {scenario}",
        xaxis_title="Time (min)", yaxis_title="Pressure (psig)",
        hovermode="x unified", template="plotly_white", height=400,
    )
    return fig


def build_flow_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"], y=df["Q_total_gpm"],
        mode="lines", name="Q_total",
        line=dict(color=COLORS["flow"], width=2),
        hovertemplate="Time: %{x:.1f} min<br>Flow: %{y:.2f} GPM<extra></extra>",
    ))
    fig.update_layout(
        title=f"Flow Rate — {scenario}",
        xaxis_title="Time (min)", yaxis_title="Flow Rate (GPM)",
        hovermode="x unified", template="plotly_white", height=400,
    )
    return fig


def build_volume_remaining_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"], y=df["V_liquid_gal"],
        mode="lines", name="V_remaining",
        line=dict(color=COLORS["remaining"], width=2),
        fill="tozeroy", fillcolor="rgba(0, 204, 150, 0.1)",
        hovertemplate="Time: %{x:.1f} min<br>Remaining: %{y:.0f} gal<extra></extra>",
    ))
    fig.update_layout(
        title=f"Volume Remaining — {scenario}",
        xaxis_title="Time (min)", yaxis_title="Volume (gal)",
        hovermode="x unified", template="plotly_white", height=400,
    )
    return fig


def build_transferred_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"], y=df["V_transferred_gal"],
        mode="lines", name="V_transferred",
        line=dict(color=COLORS["transferred"], width=2),
        fill="tozeroy", fillcolor="rgba(171, 99, 250, 0.1)",
        hovertemplate="Time: %{x:.1f} min<br>Transferred: %{y:.0f} gal<extra></extra>",
    ))
    fig.update_layout(
        title=f"Cumulative Transferred — {scenario}",
        xaxis_title="Time (min)", yaxis_title="Volume (gal)",
        hovermode="x unified", template="plotly_white", height=400,
    )
    return fig


def build_pressure_drops_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    """Per-segment pressure drop breakdown (V2 only)."""
    fig = go.Figure()
    if "dP_valve" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["time_min"], y=df["dP_valve"] / PSI_CONV,
            mode="lines", name="Valve",
            line=dict(color=COLORS["valve"], width=2),
        ))
    if "dP_seg1" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["time_min"], y=df["dP_seg1"] / PSI_CONV,
            mode="lines", name="Pipe Seg 1",
            line=dict(color=COLORS["seg1"], width=2),
        ))
    if "dP_seg2" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["time_min"], y=df["dP_seg2"] / PSI_CONV,
            mode="lines", name="Pipe Seg 2",
            line=dict(color=COLORS["seg2"], width=2),
        ))
    if "dP_drive" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["time_min"], y=df["dP_drive"] / PSI_CONV,
            mode="lines", name="Drive (total)",
            line=dict(color="#333", width=2, dash="dash"),
        ))
    fig.update_layout(
        title=f"Pressure Drop Breakdown — {scenario}",
        xaxis_title="Time (min)", yaxis_title="Pressure Drop (psi)",
        hovermode="x unified", template="plotly_white", height=400,
    )
    return fig


def build_reynolds_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    """Reynolds number per segment with regime bands (V2 only)."""
    fig = go.Figure()
    fig.add_hrect(y0=0, y1=2100, fillcolor="rgba(0,200,0,0.08)",
                  line_width=0, annotation_text="Laminar",
                  annotation_position="top left")
    fig.add_hrect(y0=2100, y1=4000, fillcolor="rgba(255,165,0,0.08)",
                  line_width=0, annotation_text="Transition",
                  annotation_position="top left")

    max_re = 5000
    for col, name, color in [
        ("Re_valve", "Valve", COLORS["valve"]),
        ("Re_pipe1", "Pipe 1", COLORS["seg1"]),
        ("Re_pipe2", "Pipe 2", COLORS["seg2"]),
    ]:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df["time_min"], y=df[col],
                mode="lines", name=name,
                line=dict(color=color, width=2),
            ))
            col_max = df[col].max()
            if col_max > max_re:
                max_re = col_max

    use_log = max_re > 10000
    fig.update_layout(
        title=f"Reynolds Number — {scenario}",
        xaxis_title="Time (min)", yaxis_title="Re",
        hovermode="x unified", template="plotly_white", height=400,
        yaxis=dict(type="log" if use_log else "linear"),
    )
    return fig


def build_liquid_level_chart(df: pd.DataFrame, scenario: str) -> go.Figure:
    """Liquid height in horizontal cylinder (V2 only)."""
    if "h_liquid" not in df.columns:
        return go.Figure().update_layout(title="No liquid level data")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time_min"], y=df["h_liquid"] * 39.3701,  # m to inches
        mode="lines", name="Liquid Height",
        line=dict(color="#FF8C00", width=2),
        fill="tozeroy", fillcolor="rgba(255, 140, 0, 0.15)",
    ))
    fig.update_layout(
        title=f"Liquid Level in Tank — {scenario}",
        xaxis_title="Time (min)", yaxis_title="Liquid Height (inches)",
        hovermode="x unified", template="plotly_white", height=400,
    )
    return fig


def build_flow_diagram(df: pd.DataFrame, time_idx: int, scenario: str) -> go.Figure:
    """Interactive system schematic with live values."""
    row = df.iloc[time_idx]
    t_min = row.get("time_min", row.get("time", 0) / 60.0)
    p_psig = row.get("P_tank_psig", 0)
    q_gpm = row.get("Q_total_gpm", 0)
    v_liq_gal = row.get("V_liquid_gal", 0)
    v_trans_gal = row.get("V_transferred_gal", 0)
    h_liq = row.get("h_liquid", 0)

    max_liq = df["V_liquid_gal"].max()
    fill_frac = v_liq_gal / max_liq if max_liq > 0 else 0

    re1 = row.get("Re_pipe1", row.get("Re", 0))
    v1 = row.get("v_pipe1", row.get("v_hose", 0))

    fig = go.Figure()
    fig.update_xaxes(range=[-0.5, 10.5], visible=False, fixedrange=True)
    fig.update_yaxes(range=[-1.5, 7.5], visible=False, fixedrange=True,
                     scaleanchor="x", scaleratio=1)

    # AIR SUPPLY
    fig.add_shape(type="rect", x0=0.5, y0=5.8, x1=2.5, y1=7.0,
                  fillcolor="#E3F2FD", line=dict(color="#1565C0", width=2))
    fig.add_annotation(x=1.5, y=6.4, text="<b>Air Compressor</b>",
                       showarrow=False, font=dict(size=12, color="#1565C0"))
    mdot = row.get("mdot_air_in", 0)
    air_status = "ON" if mdot > 0.001 else "SHUT"
    fig.add_annotation(x=1.5, y=6.0,
                       text=f"m_dot={mdot*1000:.1f} g/s ({air_status})",
                       showarrow=False, font=dict(size=10, color="#666"))
    fig.add_annotation(x=1.5, y=5.3, ax=1.5, ay=5.7,
                       arrowhead=3, arrowsize=1.5, arrowwidth=2,
                       arrowcolor="#1565C0", showarrow=True, text="")

    # TANKER
    tx0, tx1, ty0, ty1 = 0.0, 3.0, 1.5, 5.2
    fig.add_shape(type="rect", x0=tx0, y0=ty0, x1=tx1, y1=ty1,
                  fillcolor="#FFF8E1", line=dict(color="#F57F17", width=3))

    liq_top = ty0 + fill_frac * (ty1 - ty0)
    if fill_frac > 0.001:
        fig.add_shape(type="rect",
                      x0=tx0+0.05, y0=ty0+0.05, x1=tx1-0.05, y1=liq_top,
                      fillcolor="rgba(255,152,0,0.5)",
                      line=dict(color="#E65100", width=1))
    if 0.01 < fill_frac < 0.99:
        fig.add_shape(type="line",
                      x0=tx0+0.05, y0=liq_top, x1=tx1-0.05, y1=liq_top,
                      line=dict(color="#E65100", width=2, dash="dash"))

    uy = (liq_top + ty1) / 2 if fill_frac < 0.9 else ty1 - 0.2
    fig.add_annotation(x=1.5, y=min(uy, ty1-0.15),
                       text=f"<b>Ullage</b><br>{p_psig:.1f} psig",
                       showarrow=False, font=dict(size=11, color="#D84315"))
    if fill_frac > 0.05:
        ly = (ty0 + liq_top) / 2
        h_in = h_liq * 39.3701 if h_liq else 0
        fig.add_annotation(x=1.5, y=ly,
                           text=f"<b>Liquid</b><br>{v_liq_gal:.0f} gal<br>h={h_in:.1f} in",
                           showarrow=False, font=dict(size=10, color="#4E342E"))
    fig.add_annotation(x=1.5, y=ty0-0.3, text="<b>TANKER (DOT-407)</b>",
                       showarrow=False, font=dict(size=12, color="#F57F17"))

    # VALVE
    fig.add_shape(type="rect", x0=3.1, y0=1.7, x1=3.8, y1=2.3,
                  fillcolor="#FFCDD2", line=dict(color="#C62828", width=2))
    fig.add_annotation(x=3.45, y=2.0, text="<b>V</b>",
                       showarrow=False, font=dict(size=11, color="#C62828"))

    # PIPE SEG 1
    hose_y = 2.0
    fig.add_shape(type="rect", x0=3.8, y0=1.8, x1=5.5, y1=2.2,
                  fillcolor="#BBDEFB" if q_gpm > 0.1 else "#E0E0E0",
                  line=dict(color="#616161", width=2))
    fig.add_annotation(x=4.65, y=2.5, text="<b>Seg 1</b>",
                       showarrow=False, font=dict(size=9, color="#333"))

    # COUPLING
    fig.add_shape(type="rect", x0=5.5, y0=1.75, x1=5.7, y1=2.25,
                  fillcolor="#FFD54F", line=dict(color="#F57F17", width=1))

    # PIPE SEG 2
    fig.add_shape(type="rect", x0=5.7, y0=1.8, x1=7.4, y1=2.2,
                  fillcolor="#BBDEFB" if q_gpm > 0.1 else "#E0E0E0",
                  line=dict(color="#616161", width=2))
    fig.add_annotation(x=6.55, y=2.5, text="<b>Seg 2</b>",
                       showarrow=False, font=dict(size=9, color="#333"))

    # Flow arrows
    if q_gpm > 0.1:
        for ax_pos in [4.2, 5.0, 6.1, 6.9]:
            fig.add_annotation(x=ax_pos+0.3, y=hose_y, ax=ax_pos, ay=hose_y,
                               arrowhead=2, arrowsize=1, arrowwidth=2,
                               arrowcolor="#1565C0", showarrow=True, text="")
    fig.add_annotation(x=5.5, y=1.3,
                       text=f"{q_gpm:.1f} GPM | v={v1:.3f} m/s | Re={re1:.0f}",
                       showarrow=False, font=dict(size=9, color="#1565C0"))

    # RECEIVER
    fig.add_shape(type="rect", x0=7.5, y0=1.2, x1=9.5, y1=3.5,
                  fillcolor="#E8F5E9", line=dict(color="#2E7D32", width=2))
    recv_fill = v_trans_gal / max_liq if max_liq > 0 else 0
    recv_top = 1.25 + recv_fill * (3.45 - 1.25)
    if recv_fill > 0.005:
        fig.add_shape(type="rect",
                      x0=7.55, y0=1.25, x1=9.45, y1=min(recv_top, 3.45),
                      fillcolor="rgba(76,175,80,0.4)",
                      line=dict(color="#1B5E20", width=1))
    fig.add_annotation(x=8.5, y=2.7,
                       text=f"<b>Received</b><br>{v_trans_gal:.0f} gal",
                       showarrow=False, font=dict(size=11, color="#1B5E20"))
    fig.add_annotation(x=8.5, y=1.0, text="<b>RECEIVER</b>",
                       showarrow=False, font=dict(size=12, color="#2E7D32"))

    # Relief indicator
    mdot_relief = row.get("mdot_relief", 0)
    if mdot_relief > 0.0001:
        fig.add_annotation(x=2.8, y=5.4, text="<b>RELIEF OPEN</b>",
                           showarrow=False, font=dict(size=10, color="red"),
                           bgcolor="#FFCDD2", bordercolor="red",
                           borderwidth=1, borderpad=3)

    # Time badge
    fig.add_annotation(x=9.5, y=7.0, text=f"<b>t = {t_min:.1f} min</b>",
                       showarrow=False, font=dict(size=14, color="#333"),
                       bgcolor="#FFF9C4", bordercolor="#F9A825",
                       borderwidth=2, borderpad=6)

    fig.update_layout(
        title=f"System Flow Diagram — {scenario}",
        width=900, height=550, template="plotly_white",
        showlegend=False, margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="white",
    )
    return fig


def build_comparison_chart(runs_data: list[tuple[str, pd.DataFrame]]) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Tank Pressure (psig)", "Flow Rate (GPM)",
                        "Volume Remaining (gal)", "Transferred Volume (gal)"),
        horizontal_spacing=0.08, vertical_spacing=0.12,
    )
    colors = ["#EF553B", "#636EFA", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3"]
    for i, (name, df) in enumerate(runs_data):
        c = colors[i % len(colors)]
        fig.add_trace(go.Scatter(x=df["time_min"], y=df["P_tank_psig"],
                                 mode="lines", name=name, legendgroup=name,
                                 showlegend=True, line=dict(color=c, width=2)),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=df["time_min"], y=df["Q_total_gpm"],
                                 mode="lines", name=name, legendgroup=name,
                                 showlegend=False, line=dict(color=c, width=2)),
                      row=1, col=2)
        fig.add_trace(go.Scatter(x=df["time_min"], y=df["V_liquid_gal"],
                                 mode="lines", name=name, legendgroup=name,
                                 showlegend=False, line=dict(color=c, width=2)),
                      row=2, col=1)
        fig.add_trace(go.Scatter(x=df["time_min"], y=df["V_transferred_gal"],
                                 mode="lines", name=name, legendgroup=name,
                                 showlegend=False, line=dict(color=c, width=2)),
                      row=2, col=2)
    fig.update_layout(
        title="Scenario Comparison", hovermode="x unified",
        template="plotly_white", height=700,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                    xanchor="center", x=0.5),
    )
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

    st.title("🛢️ TankerTransfer V2 — Simulation Dashboard")
    st.caption("Realistic air-displacement tanker unloading simulation")

    runs = discover_runs(DATA_DIR)
    if not runs:
        st.warning(f"No simulation outputs found in `{DATA_DIR}`.")
        return

    # Sidebar: selection
    st.sidebar.header("📋 Scenario Selection")
    run_options = {r["name"]: r for r in runs}
    selected_names = st.sidebar.multiselect(
        "Select run(s):",
        options=list(run_options.keys()),
        default=[runs[-1]["name"]] if runs else [],
    )
    if not selected_names:
        st.info("Select at least one run from the sidebar.")
        return
    selected_runs = [run_options[n] for n in selected_names]

    # Sidebar: view mode
    st.sidebar.header("📊 View Mode")
    view_mode = st.sidebar.radio(
        "Display mode:",
        options=["Individual Charts", "Comparison Overlay",
                 "System Flow Diagram", "Engineering Detail"],
    )

    # Load data
    runs_data = []
    for run_info in selected_runs:
        try:
            df = load_csv(run_info["csv_path"])
            runs_data.append((run_info["scenario"], df, run_info))
        except Exception as e:
            st.error(f"Failed to load {run_info['name']}: {e}")
    if not runs_data:
        st.error("No data loaded.")
        return

    # ─── Comparison ──────────────────────────────────────────────────
    if view_mode == "Comparison Overlay":
        st.header("Scenario Comparison")
        fig = build_comparison_chart([(n, d) for n, d, _ in runs_data])
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Summary")
        rows_summary = []
        for name, df, _ in runs_data:
            rows_summary.append({
                "Scenario": name,
                "Peak P (psig)": f"{df['P_tank_psig'].max():.1f}",
                "Peak Q (GPM)": f"{df['Q_total_gpm'].max():.1f}",
                "Transferred (gal)": f"{df['V_transferred_gal'].iloc[-1]:.0f}",
                "Remaining (gal)": f"{df['V_liquid_gal'].iloc[-1]:.0f}",
                "Time (min)": f"{df['time'].iloc[-1]/60:.1f}",
            })
        st.table(pd.DataFrame(rows_summary))

    # ─── System Flow Diagram ─────────────────────────────────────────
    elif view_mode == "System Flow Diagram":
        for name, df, _ in runs_data:
            st.header(f"System Flow — {name}")
            max_idx = len(df) - 1
            time_idx = st.slider(
                f"Time step ({name})", 0, max_idx,
                value=min(max_idx // 10, max_idx),
                key=f"flow_{name}",
            )
            row = df.iloc[time_idx]
            st.write(f"**Time:** {row.get('time',0):.0f}s ({row.get('time',0)/60:.1f} min)")

            fig = build_flow_diagram(df, time_idx, name)
            st.plotly_chart(fig, use_container_width=True)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Pressure", f"{row.get('P_tank_psig',0):.1f} psig")
            c2.metric("Flow", f"{row.get('Q_total_gpm',0):.1f} GPM")
            c3.metric("Remaining", f"{row.get('V_liquid_gal',0):.0f} gal")
            c4.metric("Transferred", f"{row.get('V_transferred_gal',0):.0f} gal")
            h_in = row.get("h_liquid", 0) * 39.3701 if "h_liquid" in df.columns else 0
            c5.metric("Liquid Level", f"{h_in:.1f} in")
            st.divider()

    # ─── Engineering Detail (V2 only) ────────────────────────────────
    elif view_mode == "Engineering Detail":
        for name, df, _ in runs_data:
            st.header(f"Engineering Detail — {name}")

            col1, col2 = st.columns(2)
            with col1:
                if "dP_valve" in df.columns:
                    st.plotly_chart(build_pressure_drops_chart(df, name),
                                   use_container_width=True)
                else:
                    st.info("Pressure drop data not available (V1 run?)")
            with col2:
                if "Re_pipe1" in df.columns:
                    st.plotly_chart(build_reynolds_chart(df, name),
                                   use_container_width=True)
                else:
                    st.info("Reynolds data not available (V1 run?)")

            col3, col4 = st.columns(2)
            with col3:
                st.plotly_chart(build_liquid_level_chart(df, name),
                               use_container_width=True)
            with col4:
                if "mdot_air_in" in df.columns:
                    fig_air = go.Figure()
                    fig_air.add_trace(go.Scatter(
                        x=df["time_min"], y=df["mdot_air_in"] * 1000,
                        mode="lines", name="Air In",
                        line=dict(color="#1565C0", width=2),
                    ))
                    if "mdot_relief" in df.columns:
                        fig_air.add_trace(go.Scatter(
                            x=df["time_min"], y=df["mdot_relief"] * 1000,
                            mode="lines", name="Relief Out",
                            line=dict(color="#C62828", width=2, dash="dash"),
                        ))
                    fig_air.update_layout(
                        title=f"Air Mass Flow — {name}",
                        xaxis_title="Time (min)",
                        yaxis_title="Mass Flow (g/s)",
                        hovermode="x unified", template="plotly_white",
                        height=400,
                    )
                    st.plotly_chart(fig_air, use_container_width=True)

            st.divider()

    # ─── Individual Charts ───────────────────────────────────────────
    elif view_mode == "Individual Charts":
        for name, df, run_info in runs_data:
            st.header(f"📈 {name}")

            meta = run_info.get("metadata", {})
            if meta:
                with st.expander("Run Metadata", expanded=False):
                    st.json(meta)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Peak Pressure", f"{df['P_tank_psig'].max():.1f} psig")
            c2.metric("Peak Flow", f"{df['Q_total_gpm'].max():.1f} GPM")
            c3.metric("Transferred", f"{df['V_transferred_gal'].iloc[-1]:.0f} gal")
            c4.metric("Remaining", f"{df['V_liquid_gal'].iloc[-1]:.0f} gal")

            ch1, ch2 = st.columns(2)
            with ch1:
                st.plotly_chart(build_pressure_chart(df, name),
                               use_container_width=True)
                st.plotly_chart(build_volume_remaining_chart(df, name),
                               use_container_width=True)
            with ch2:
                st.plotly_chart(build_flow_chart(df, name),
                               use_container_width=True)
                st.plotly_chart(build_transferred_chart(df, name),
                               use_container_width=True)
            st.divider()

    # Sidebar info
    st.sidebar.header("ℹ️ Info")
    st.sidebar.write(f"**Data dir:** `{DATA_DIR}`")
    st.sidebar.write(f"**Runs:** {len(runs)}")
    for r in runs:
        st.sidebar.write(f"- {r['scenario']}")


if __name__ == "__main__":
    main()
