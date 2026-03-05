# RUNBOOK

## Operational Procedures for Sim-Lab Environment

**Project Location:** `/opt/sim-lab/truck-tanker-sim-env`

> ⚠️ ALL commands must be run from the project directory unless stated otherwise.

---

## 1. How to Run Simulations

### Full Pipeline (Recommended)

```bash
cd /opt/sim-lab/truck-tanker-sim-env
./scripts/run_all.sh
```

This will:
1. Capture baseline Docker state snapshot
2. Run Modelica simulation (compile + execute HelloWorld)
3. Run Python visualization (CSV → PNG)
4. Run guard integrity check
5. Log results to `logs/EXECUTION_LOG.md`

### Individual Steps

#### Run Modelica Simulation Only

```bash
cd /opt/sim-lab/truck-tanker-sim-env
docker compose run --rm openmodelica
```

#### Run Python Visualization Only

```bash
cd /opt/sim-lab/truck-tanker-sim-env
docker compose run --rm python-viz
```

---

## 2. How to Run Integrity Checks

### Capture Baseline Snapshot

```bash
cd /opt/sim-lab/truck-tanker-sim-env
./scripts/guard_check.sh --snapshot
```

This saves current Docker state to `_guard/*_before.txt`.

### Verify Integrity (After Operations)

```bash
cd /opt/sim-lab/truck-tanker-sim-env
./scripts/guard_check.sh --verify
```

This compares current state against the baseline. Output:

- `✅ PASS` — no unexpected changes detected
- `❌ FAIL` — unexpected changes found (details printed)

---

## 3. How to Check Container Status

### View Sim-Lab Containers Only

```bash
docker compose -p simlab ps -a
```

### View ALL Containers (Including Production)

```bash
docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
```

### Verify Production Containers Are Running

```bash
for c in hmdm hmdm-db root-n8n-1 root-traefik-1; do
  echo -n "$c: "
  docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo "NOT FOUND"
done
```

---

## 4. How to View Simulation Outputs

### Output Files

| File | Location | Description |
|------|----------|-------------|
| CSV results | `outputs/HelloWorld_res.csv` | Raw simulation data |
| PNG plot | `outputs/HelloWorld_plot.png` | Visualization |

### Copy Output to Local Machine (From Your PC)

```bash
scp root@<vps-ip>:/opt/sim-lab/truck-tanker-sim-env/outputs/HelloWorld_plot.png .
```

---

## 5. Troubleshooting

### Problem: Simulation Container Fails to Start

```bash
# Check if image was pulled
docker images | grep openmodelica

# If not, pull manually
docker compose pull openmodelica

# Check container logs
docker compose logs openmodelica
```

### Problem: Guard Check Fails

```bash
# View the diff
diff _guard/containers_before.txt _guard/containers_after.txt
diff _guard/networks_before.txt _guard/networks_after.txt
diff _guard/volumes_before.txt _guard/volumes_after.txt

# If only sim-lab containers changed, that's expected — guard handles this
# If production containers changed, STOP and investigate
```

### Problem: Port Conflict

This should never happen (we publish no ports). If it does:

```bash
# Check what's using ports
ss -tlnp | grep -E ':(80|443|5678|8080|31000)\s'
```

### Problem: Disk Space Low

```bash
# Check usage
df -h /

# Remove sim-lab outputs only
rm -rf /opt/sim-lab/truck-tanker-sim-env/outputs/*

# Remove sim-lab images only (get IDs first)
docker images | grep -E 'openmodelica|python'
docker rmi <specific-image-id>
```

> ⚠️ **NEVER** run `docker system prune` — see RISK_AND_ISOLATION.md

---

## 6. Recovery Procedures

### If a Production Container Goes Down

**This is the #1 priority.** Stop all sim-lab work immediately.

```bash
# Check which container is down
docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -E 'hmdm|n8n|traefik'

# Restart the specific container
docker start <container-name>

# Verify it's healthy
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### If Sim-Lab Needs Complete Removal

```bash
cd /opt/sim-lab/truck-tanker-sim-env
docker compose down --rmi local    # Stop containers, remove project images only
# Verify production is untouched
docker ps -a
docker network ls
docker volume ls
```

### If You Need to Start Over

```bash
cd /opt/sim-lab/truck-tanker-sim-env
docker compose down
rm -rf outputs/* _guard/*_after.txt
# Re-run baseline
./scripts/guard_check.sh --snapshot
```

---

# APPLICATION RUNBOOK (TankerTransfer)

## 7. Running TankerTransfer Scenarios

### Run All 3 Scenarios (Recommended)

```bash
cd /opt/sim-lab/truck-tanker-sim-env
./scripts/run_app.sh
```

This executes:
1. Guard baseline snapshot
2. Scenario A (pressurize only) → simulate → plot
3. Scenario B (split air) → simulate → plot
4. Scenario C (pump only) → simulate → plot
5. Comparison report generation
6. Guard integrity verification
7. Logs results to `logs/EXECUTION_LOG.md`

### Run a Single Scenario

```bash
cd /opt/sim-lab/truck-tanker-sim-env

# Scenario A only
./scripts/run_app.sh scenario_A_pressurize_only

# Scenario B only
./scripts/run_app.sh scenario_B_split_air

# Scenario C only
./scripts/run_app.sh scenario_C_pump_only
```

### Run Simulation Manually (Step by Step)

```bash
cd /opt/sim-lab/truck-tanker-sim-env

# Step 1: Run simulation
docker compose run --rm openmodelica-runner \
    bash /work/scripts/run_scenario.sh /work/config/scenario_A_pressurize_only.yaml

# Step 2: Find the output directory
ls -td data/runs/*_scenario_A*/ | head -1

# Step 3: Generate plots
docker compose run --rm python-plotter \
    "pip install --quiet matplotlib && python /work/python/plot_results.py /work/data/runs/<TIMESTAMP>_scenario_A_pressurize_only/outputs.csv"

# Step 4: Generate comparison report
docker compose run --rm python-plotter \
    "pip install --quiet matplotlib && python /work/python/make_report.py /work/data/runs"
```

## 8. Customizing Scenarios

### Edit Parameters (No Code Changes Needed)

All parameters live in YAML config files under `config/`:

```bash
# Edit scenario A parameters
nano config/scenario_A_pressurize_only.yaml
```

Key parameters you can change:
- `tanker_total_volume_gal` — tank size
- `air_supply_scfm` — compressor capacity
- `max_tank_pressure_psig` — pressure limit
- `hose_ID_in` — hose diameter
- `viscosity_cP` — liquid viscosity
- `receiver_backpressure_psig` — back pressure

### Create a Custom Scenario

1. Copy an existing config:
   ```bash
   cp config/scenario_A_pressurize_only.yaml config/scenario_custom.yaml
   ```
2. Edit the copy — change `scenario_name` and desired parameters
3. Run it:
   ```bash
   docker compose run --rm openmodelica-runner \
       bash /work/scripts/run_scenario.sh /work/config/scenario_custom.yaml
   ```

## 9. Viewing Results

### Output Structure

Each run creates a timestamped directory:
```
data/runs/20260220_153000_scenario_A_pressurize_only/
├── inputs.yaml       # Copy of config used
├── outputs.csv       # Simulation results (time series)
├── plots.png         # 4-panel visualization
└── run_log.json      # Run metadata and parameters
```

### View Comparison Report

After running all scenarios:
```
data/runs/comparison_report.txt   # Text summary table
data/runs/comparison_report.html  # HTML table (open in browser)
```

### Copy Results to Local Machine

```bash
scp -r root@<vps-ip>:/opt/sim-lab/truck-tanker-sim-env/data/runs/ ./local_runs/
```

## 10. Resource Limits

All simulation containers are limited to prevent starving production:

| Service | CPU Limit | Memory Limit |
|---------|-----------|-------------|
| openmodelica-runner | 1.0 core | 1 GB |
| python-plotter | 1.0 core | 1 GB |

Monitor usage during a run:
```bash
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

## 11. Interactive Dashboard

### Start the Dashboard

```bash
cd /opt/sim-lab/truck-tanker-sim-env
docker compose up -d visual-dashboard
```

The dashboard runs as a long-lived background service (unlike simulation containers
which are `--rm` ephemeral). It will auto-restart if the container crashes.

### Verify Dashboard is Running

```bash
docker compose ps visual-dashboard
```

Expected:
```
NAME                SERVICE              STATUS    PORTS
simlab-dashboard    visual-dashboard     running   127.0.0.1:8501->8501/tcp
```

### Access via SSH Tunnel

From your **local machine** (not the VPS):

```bash
ssh -L 8501:localhost:8501 user@your-vps-ip
```

Then open in your browser: `http://localhost:8501`

### Stop the Dashboard

```bash
docker compose stop visual-dashboard
```

### Restart the Dashboard

```bash
docker compose restart visual-dashboard
```

### View Dashboard Logs

```bash
docker compose logs visual-dashboard --tail 50
docker compose logs visual-dashboard -f   # Follow live
```

### Dashboard Lifecycle

| Action | Command |
|--------|---------|
| Start (background) | `docker compose up -d visual-dashboard` |
| Stop | `docker compose stop visual-dashboard` |
| Restart | `docker compose restart visual-dashboard` |
| View logs | `docker compose logs visual-dashboard` |
| Check status | `docker compose ps visual-dashboard` |
| Remove container | `docker compose rm -f visual-dashboard` |

> **Note:** The dashboard reads simulation data in **read-only** mode.
> You can start/stop it at any time without affecting simulation runs.
> New simulation results appear automatically after refreshing the browser.

---

## 12. Running Parametric Sweeps

### Available Sweep Scripts

| Script | Sweep | Description |
|--------|-------|-------------|
| `scripts/run_parametric_sweep.sh` | A–D | Single-variable sweeps (volume, pressure, temperature, SCFM) |
| `scripts/run_hose_sweep.sh` | E | Hose diameter × SCFM grid (2D) |
| `scripts/run_viscosity_sweep.sh` | F | Viscosity 1–2000 cP |
| `scripts/run_visc_scfm_sweep.sh` | G | Viscosity × Compressor grid (2D) |
| `scripts/run_mega_sweep.sh` | H | 5D mega combo (1,080 simulations) |

### Run a Single-Variable Sweep

```bash
cd /opt/sim-lab/truck-tanker-sim-env
bash scripts/run_parametric_sweep.sh
```

Runs Sweeps A–D sequentially (200 sims total, ~30 min).

### Run the 5D Mega Sweep

```bash
cd /opt/sim-lab/truck-tanker-sim-env
nohup bash scripts/run_mega_sweep.sh > /tmp/mega_sweep.log 2>&1 &
```

Monitor progress:
```bash
tail -5 /tmp/mega_sweep.log
grep -c "^RUN" /tmp/mega_sweep.log   # Count completed sims
```

Expected: 1,080 simulations in ~125 minutes.

### Sweep Output

All results are saved to `data/parametric_sweeps/`:
```
data/parametric_sweeps/
├── A_liquid_volume.csv        # 50 rows
├── B_tank_pressure.csv        # 50 rows
├── C_gas_temperature.csv      # 50 rows
├── D_compressor_scfm.csv      # 50 rows
├── E_hose_diameter_multi.csv  # 100 rows
├── F_viscosity.csv            # 50 rows
├── G_visc_scfm_combo.csv     # 100 rows
├── H_mega_combo.csv           # 1,080 rows
└── Master_Sweep_Report.xlsx   # All data, 9 sheets
```

### Generate Master Excel Report

```bash
docker exec simlab-dashboard python3 /work/scripts/build_master_report.py
```

Output: `data/parametric_sweeps/Master_Sweep_Report.xlsx` (~113 KB, 9 sheets).

### Download Report to Local Machine

```bash
# From your Mac terminal:
scp root@31.220.52.220:/opt/sim-lab/truck-tanker-sim-env/data/parametric_sweeps/Master_Sweep_Report.xlsx ~/Downloads/
```

Or use the **persistent file server** on port 8502:
```
http://<VPS-IP>:8502/
```
All files in `data/downloads/` are served here. Drop any PDF/CSV/PNG into that
directory and it is instantly available at a stable URL (no temporary servers needed).

---

## 12a. File Server — Persistent Download Links

### Overview

Port **8502** runs a persistent file server for special-case reports
(pump analyses, driver forms, etc.). This is **separate** from the
dashboard's simulation PDF export feature on port 8501.

### Service Details

| Property | Value |
|----------|-------|
| Container | `simlab-file-server` |
| Port | `0.0.0.0:8502` |
| Serve directory | `data/downloads/` |
| Auto-restart | Yes (`unless-stopped`) |
| Resources | CPU: 0.25, Memory: 128 MB |

### Start / Stop

```bash
cd /opt/sim-lab/truck-tanker-sim-env

# Start
docker compose up -d file-server

# Stop
docker compose stop file-server

# Restart
docker compose restart file-server

# View logs
docker logs simlab-file-server
```

### Access

```
# Browse all downloads
http://<VPS-IP>:8502/

# Direct link to a specific file
http://<VPS-IP>:8502/Pump_Analysis_Report.pdf
```

### Adding Files

Drop files into `data/downloads/` — they appear instantly:

```bash
# Copy a file into the downloads directory
cp /path/to/report.pdf /opt/sim-lab/truck-tanker-sim-env/data/downloads/

# Or generate a report directly there
python3 python/pump_report.py data/downloads/Pump_Analysis_Report.pdf
```

### Currently Served Files

| File | Description |
|------|-------------|
| `Pump_Analysis_Report.pdf` | Pump suitability analysis (Predator 212cc) |
| `Driver_Unloading_Data_Form.pdf` | Driver unloading data collection form |
| `Driver_Unloading_Sheet_V2.pdf` | Driver reference sheet |

---

## 13. Dashboard Features

### Company Logo

Upload a company logo to appear in the sidebar above the title:

1. Open dashboard → **ℹ️ System Info** → **Company Logo**
2. Click **Browse files** → select your logo (PNG/JPG/SVG)
3. Refresh the page

Logo is stored at `data/assets/logo.png` (writable mount).

Alternatively, copy directly:
```bash
scp logo.png root@<VPS-IP>:/opt/sim-lab/truck-tanker-sim-env/data/assets/logo.png
docker compose restart visual-dashboard
```

### Pre-Pressurization Time Calculator

When **Starting Pressure > 0 psig** is entered in the Tank tab:

1. The dashboard calculates how long it takes to pump air from 0 → target pressure
2. Shows the estimate above the Run button using the actual SCFM value
3. After simulation completes, results display:
   - **Pressurize Time (min)** — time to reach target pressure
   - **Total Realistic Time (min)** — pressurize + valve-open transfer time

Formula: `time = (headspace_ft³ × target_psig / 14.696) / SCFM`

> **Engineering Note:** 1,080 simulations proved that pre-pressurizing **never helps**.
> 0 psig always produces the fastest total time. The compressor is better used
> pushing liquid out immediately rather than building pressure first.
