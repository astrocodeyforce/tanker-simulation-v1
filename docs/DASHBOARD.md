# DASHBOARD — Interactive Visualization

## Overview

The TankerTransfer application includes an **interactive web dashboard** built with
[Streamlit](https://streamlit.io/) and [Plotly](https://plotly.com/python/). It
provides browser-based exploration of simulation results with zoom, pan, and
hover-to-inspect capabilities.

---

## Security Model

### Localhost-Only Port Binding

The dashboard Docker service binds its port:

```yaml
ports:
  - "0.0.0.0:8501:8501"
```

| Aspect | Detail |
|--------|--------|
| **Host binding** | `0.0.0.0` (all interfaces) |
| **Container port** | `8501` (Streamlit default) |
| **Public exposure** | Yes — accessible via VPS IP |
| **Access method** | Direct browser or SSH tunnel |

### Why NOT `8501:8501`?

When Docker sees `"8501:8501"` (without an IP prefix), it binds to `0.0.0.0` —
meaning **all network interfaces**, including the public-facing one. This would
expose the dashboard to anyone who can reach the VPS on port 8501.

By prefixing with `127.0.0.1:`, the port is **only accessible from the VPS
itself**. External access requires an authenticated SSH session, providing an
additional layer of security without any firewall changes.

### Explicitly Forbidden Configurations

| Configuration | Risk Level | Reason |
|--------------|------------|--------|
| `"8501:8501"` | **CRITICAL** | Binds to 0.0.0.0 — publicly accessible |
| `"0.0.0.0:8501:8501"` | **CRITICAL** | Explicitly public binding |
| `network_mode: host` | **CRITICAL** | Bypasses Docker networking entirely |
| No firewall changes | Required | Port 8501 must NOT be opened in UFW/iptables |

---

## How to Access the Dashboard

### Step 1: Start the Dashboard

```bash
cd /opt/sim-lab/truck-tanker-sim-env
docker compose up -d visual-dashboard
```

Verify it is running:

```bash
docker compose ps visual-dashboard
```

Expected output:
```
NAME                SERVICE              STATUS    PORTS
simlab-dashboard    visual-dashboard     running   127.0.0.1:8501->8501/tcp
```

### Step 2: Create an SSH Tunnel (from your local machine)

```bash
ssh -L 8501:localhost:8501 user@your-vps-ip
```

This forwards your local port 8501 to the VPS's localhost:8501 through the
encrypted SSH connection.

### Step 3: Open in Browser

Navigate to:

```
http://localhost:8501
```

You will see the TankerTransfer dashboard with:
- Sidebar for scenario selection
- Interactive Plotly charts (pressure, flow, volume, transferred)
- Zoom/pan/hover capabilities
- Summary statistics

### Step 4: Stop the Dashboard (when done)

```bash
docker compose stop visual-dashboard
```

---

## Dashboard Features

### Scenario Selection

The sidebar lists all simulation runs found in `data/runs/`. Select one or more
runs to visualize.

### View Modes

| Mode | Description |
|------|-------------|
| **Individual Charts** | Detailed per-scenario view with 4 charts and metrics |
| **Comparison Overlay** | All selected scenarios on a single 4-panel chart |

### Interactive Charts

All charts support:
- **Zoom:** Click and drag to zoom into a region
- **Pan:** Shift+drag to pan across the chart
- **Hover:** Mouse over data points for precise values
- **Reset:** Double-click to reset zoom/pan
- **Download:** Camera icon to save chart as PNG

### Charts Available

| Chart | X-Axis | Y-Axis | Description |
|-------|--------|--------|-------------|
| Tank Pressure | Time (min) | Pressure (psig) | Ullage gas pressure |
| Flow Rate | Time (min) | Flow (GPM) | Instantaneous liquid discharge |
| Volume Remaining | Time (min) | Volume (gal) | Liquid still in tanker |
| Transferred Volume | Time (min) | Volume (gal) | Cumulative liquid delivered |

### Company Logo

The sidebar displays a company logo above the "🛢️ TankerTransfer V2" title.

**How to upload:**
1. Go to **ℹ️ System Info** page
2. Scroll to **Company Logo** section
3. Click **Browse files** and select your logo (PNG, JPG, SVG, or WebP)
4. Refresh the page — the logo appears in the sidebar

**Storage:** `data/assets/logo.png` (writable Docker mount at `/work/data/assets/`).

**Alternative (CLI):**
```bash
scp logo.png root@<VPS-IP>:/opt/sim-lab/truck-tanker-sim-env/data/assets/logo.png
docker compose restart visual-dashboard
```

### Pre-Pressurization Time Calculator

When **Starting Pressure (psig) > 0** is set in the Tank tab:

- An info box appears above the Run button showing the estimated pressurization time
- Uses the **actual SCFM value** from the Air Supply tab (dynamic, not hardcoded)
- Formula: `time_min = (headspace_ft³ × target_psig / 14.696) / SCFM`

After simulation completes, results include two additional metrics:
- **Pressurize Time (min)** — time to pump air from 0 → starting pressure
- **Total Realistic Time (min)** — pressurize time + valve-open transfer time

> **Note:** 1,080 parametric simulations proved pre-pressurizing always hurts.
> 0 psig produces the fastest total time in every tested combination.

### Run Simulation Page

The dashboard supports full simulation configuration with tabbed input:

| Tab | Parameters |
|-----|-----------|
| 🛢️ Tank | Capacity, diameter, length, fill level, starting pressure, temperature, safety valves |
| 💧 Liquid | Density, viscosity (with reference table) |
| 💨 Air Supply | Compressor SCFM |
| 🔧 Valve | Size, K-factor, opening fraction |
| 🔩 Piping | Up to 5 segments: diameter, length, roughness, fittings K |
| 📐 Discharge | Elevation change, receiver pressure |
| ⚙️ Simulation | Max run time, output interval, stop threshold |

Includes three built-in presets (Baseline, Solvent, Coating) plus Custom mode.

### PDF Report Download

The dashboard generates on-demand PDF reports from simulation results:

1. Run a simulation (or select a past result)
2. Click **📄 Download PDF Report** in the Export section
3. A multi-page PDF is generated with all active charts

**Technical pipeline:** Plotly → kaleido 0.2.1 → PNG → matplotlib PdfPages → PDF

> **Note:** This is the **simulation PDF** feature. For special-case reports
> (pump analyses, driver forms), use the **file server** on port 8502.

### Dynamic N-Pipe Support

Charts auto-detect the number of active pipe segments (1–5) based on
pressure drop data (`dP > 0.01`). Pressure drop and Reynolds number charts
automatically scale to show only the segments that are configured.

| Segment | Color |
|---------|-------|
| Seg 1 | Green |
| Seg 2 | Orange-Red |
| Seg 3 | Orange |
| Seg 4 | Purple |
| Seg 5 | Brown |

### Auto-Trim Charts

Time-series charts automatically trim to the meaningful window:
- Transfer phase (while liquid is flowing)
- Pressure climb to 95% of maximum
- Plus 1 minute margin

This eliminates hundreds of minutes of flat lines after transfer completes.

---

## Isolation Guarantees

| Property | Value |
|----------|-------|
| Container name | `simlab-dashboard` |
| Network | `simlab_network` (project-internal) |
| Port binding | `0.0.0.0:8501` |
| Python source | **Read-only** (`:ro` mount at `/work/python`) |
| Data directory | **Read-write** (at `/work/data` — for logo, configs, results) |
| Resource limits | CPU: 1.0, Memory: 1 GB |
| Privileged mode | **No** |
| Host network | **No** |

The dashboard:
- **Never modifies** simulation data (read-only bind mount)
- **Never interferes** with production containers (simlab project isolation)
- **Never exposes** ports publicly (localhost-only binding)
- **Never requires** firewall changes (SSH tunnel handles access)

---

## Troubleshooting

### Dashboard won't start

```bash
# Check logs
docker compose logs visual-dashboard

# Check if port is already in use
ss -tlnp | grep 8501

# Restart
docker compose restart visual-dashboard
```

### No simulation data shown

Run simulations first:
```bash
cd /opt/sim-lab/truck-tanker-sim-env
./scripts/run_app.sh
```

Then refresh the dashboard in your browser.

### SSH tunnel not working

```bash
# Verify the tunnel is established
ssh -L 8501:localhost:8501 user@vps-ip -v

# On the VPS, verify the dashboard is listening
ss -tlnp | grep 8501
# Expected: 127.0.0.1:8501
```

### Container resource issues

```bash
# Check resource usage
docker stats simlab-dashboard --no-stream
```
