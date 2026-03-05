# SYSTEM ARCHITECTURE

## Overview

This project runs as a **completely isolated Docker Compose stack** on a production VPS.
It shares the Docker Engine but has zero overlap with existing containers, networks, or volumes.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HOSTINGER VPS                                │
│                   Ubuntu 24.04.3 LTS (Noble)                        │
│                  Docker 28.5.1 / Compose 2.40.2                     │
│                                                                     │
│  ┌─────────────────────────────────┐  ┌──────────────────────────┐  │
│  │   PRODUCTION (DO NOT TOUCH)     │  │   SIM-LAB PROJECT        │  │
│  │                                 │  │   (Fully Isolated)       │  │
│  │  ┌───────┐  ┌────────┐         │  │                          │  │
│  │  │ hmdm  │  │ hmdm-db│         │  │  ┌──────────────────┐   │  │
│  │  │ :8080 │  │ :5432  │         │  │  │  openmodelica    │   │  │
│  │  └───┬───┘  └───┬────┘         │  │  │  (simulation)    │   │  │
│  │      │          │               │  │  │  NO PORTS        │   │  │
│  │      └──────────┘               │  │  └────────┬─────────┘   │  │
│  │   net: headwind-mdm_hmdm_internal│  │           │ shared vol  │  │
│  │                                 │  │  ┌────────┴─────────┐   │  │
│  │  ┌──────────┐  ┌───────────┐   │  │  │  python-viz      │   │  │
│  │  │ n8n      │  │ traefik   │   │  │  │  (visualization) │   │  │
│  │  │ :5678    │  │ :80/:443  │   │  │  │  NO PORTS        │   │  │
│  │  └──────────┘  └───────────┘   │  │  └──────────────────┘   │  │
│  │   net: root_default             │  │                          │  │
│  │                                 │  │  ┌──────────────────┐   │  │
│  │   vols: hmdm_pgdata, hmdm_work │  │  │  dashboard       │   │  │
│  │         n8n_data, traefik_data  │  │  │  :8501 (Streamlit)│  │  │
│  └─────────────────────────────────┘  │  └──────────────────┘   │  │
│                                       │                          │  │
│                                       │  ┌──────────────────┐   │  │
│                                       │  │  file-server     │   │  │
│                                       │  │  :8502 (Downloads)│  │  │
│                                       │  └──────────────────┘   │  │
│                                       │                          │  │
│                                       │  net: simlab_network     │  │
│                                       │  vols: bind mounts only  │  │
│                                       │  /opt/sim-lab/...        │  │
│                                       └──────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     DOCKER ENGINE                               ││
│  │  Shared kernel, but projects are COMPLETELY ISOLATED             ││
│  │  - Separate COMPOSE_PROJECT_NAME                                 ││
│  │  - Separate networks (no external)                               ││
│  │  - Separate volumes (bind mounts only)                           ││
│  │  - Published ports: 8501 (dashboard), 8502 (file server)         ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Descriptions

### 1. VPS Host Layer

| Property | Value |
|----------|-------|
| OS | Ubuntu 24.04.3 LTS (Noble Numbat) |
| Docker | 28.5.1 |
| Compose | 2.40.2 |
| Disk | 30G used / 163G free (16%) |
| RAM | 2.9Gi used / 15Gi total |

### 2. Dedicated Compose Project

| Property | Value |
|----------|-------|
| COMPOSE_PROJECT_NAME | `simlab` |
| Project Root | `/opt/sim-lab/truck-tanker-sim-env` |
| Network | `simlab_network` (internal bridge) |
| Ports Published | `8501` (dashboard), `8502` (file server) |
| External Networks | **NONE** |

### 3. OpenModelica Container

| Property | Value |
|----------|-------|
| Image | `openmodelica/openmodelica:v1.23.1-ompython` |
| Role | Compile & run Modelica models headlessly |
| Volumes | Bind mount: `./models:/work/models`, `./outputs:/work/outputs` |
| Network | `simlab_network` only |
| Ports | NONE |
| Entrypoint | Overridden to run simulation script |

### 4. Python Visualization Container

| Property | Value |
|----------|-------|
| Image | `python:3.12-slim` |
| Role | Read simulation CSV output → generate PNG plots |
| Volumes | Bind mount: `./outputs:/work/outputs`, `./scripts:/work/scripts` |
| Network | `simlab_network` only |
| Ports | NONE |

### 5. File Server Container

| Property | Value |
|----------|-------|
| Image | `python:3.12-slim` |
| Container name | `simlab-file-server` |
| Role | Serve downloadable reports (PDFs, PNGs, CSVs) on a stable URL |
| Volumes | Bind mount: `./python:/work/python:ro`, `./data:/work/data` |
| Network | `simlab_network` only |
| Ports | `0.0.0.0:8502:8502` |
| Serve directory | `data/downloads/` |
| Resources | CPU: 0.25, Memory: 128 MB |
| Restart | `unless-stopped` |

### 6. Guard / Integrity Verification Layer

| Property | Value |
|----------|-------|
| Location | `_guard/` directory |
| Purpose | Snapshot Docker state before/after runs |
| Mechanism | Diff containers, networks, volumes pre vs. post |
| New images | Allowed (pulling sim images is expected) |
| Script | `scripts/guard_check.sh` |

---

## Data Flow

```
┌────────────┐     compile      ┌────────────┐     read CSV     ┌───────────┐
│  .mo model │ ──────────────►  │  .csv data │ ──────────────►  │  .png plot│
│  (models/) │   OpenModelica   │ (outputs/) │   Python viz     │ (outputs/)│
└────────────┘                  └────────────┘                  └───────────┘
```

### Execution Sequence

```
1. guard_check.sh --snapshot        (capture baseline)
2. docker compose run openmodelica  (compile + simulate)
3. docker compose run python-viz    (generate plots)
4. guard_check.sh --verify          (integrity check)
5. Log results to EXECUTION_LOG.md
```

---

## Isolation Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| Network isolation | Dedicated `simlab_network`, no `external: true` |
| Volume isolation | Bind mounts under `/opt/sim-lab/` only, no named Docker volumes |
| Port isolation | Only 8501 (dashboard) and 8502 (file server) published |
| Naming isolation | `COMPOSE_PROJECT_NAME=simlab` prevents collisions |
| State verification | Guard script diffs before/after snapshots |
