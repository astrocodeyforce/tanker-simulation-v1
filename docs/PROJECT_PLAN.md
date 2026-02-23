# PROJECT PLAN

## Project Objective

We are building a **fully isolated simulation lab** on a production Hostinger VPS.

- **Purpose:** Dynamic tanker pressurization & liquid transfer modeling (future phases)
- **Current Phase:** Environment setup ONLY — no physics modeling, no fluid dynamics
- **Approach:** Docker-based isolation with zero interference to existing production services

---

## Scope Definition

### ✅ IN SCOPE (Current Phase — Environment Setup)

| Item | Description |
|------|-------------|
| Docker isolation architecture | Dedicated compose project, network, volumes |
| OpenModelica runtime container | Headless Modelica simulation execution |
| Python visualization container | CSV → PNG plotting pipeline |
| Integrity guard system | Pre/post verification of Docker state |
| HelloWorld validation model | Minimal model to prove the pipeline works |

### ❌ OUT OF SCOPE (Future Phases — Not Implemented Now)

| Item | Reason |
|------|--------|
| Tanker physics model | Requires validated environment first |
| Pump modeling | Future phase |
| Fluid dynamics implementation | Future phase |
| Production container modifications | FORBIDDEN — see RULES.md |

---

## Non-Negotiable Constraints

| # | Constraint | Rationale |
|---|-----------|-----------|
| 1 | **No published ports** | Prevents conflicts with Traefik (80/443), n8n (5678), HMDM (8080/31000) |
| 2 | **No modification of existing Docker stacks** | hmdm, hmdm-db, root-n8n-1, root-traefik-1 are production-critical |
| 3 | **No global Docker prune/system changes** | Could destroy production volumes/networks |
| 4 | **Everything project-scoped** | Unique COMPOSE_PROJECT_NAME, dedicated network, project-only bind mounts |
| 5 | **No privileged mode** | Security — no elevated access needed |
| 6 | **No host networking** | Must use dedicated bridge network only |

---

## Existing Production Containers (DO NOT TOUCH)

| Container | Image | Ports | Network |
|-----------|-------|-------|---------|
| hmdm | headwindmdm/hmdm:latest | 127.0.0.1:8080, 127.0.0.1:31000 | headwind-mdm_hmdm_internal |
| hmdm-db | postgres:15-alpine | 5432 (internal) | headwind-mdm_hmdm_internal |
| root-n8n-1 | docker.n8n.io/n8nio/n8n | 127.0.0.1:5678 | root_default |
| root-traefik-1 | traefik | 0.0.0.0:80, 0.0.0.0:443 | root_default |

---

## Phase Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Documentation & Control System | ✅ Complete |
| 2 | Baseline System Snapshot | ✅ Complete |
| 3 | Isolated Docker Environment | ✅ Complete |
| 4 | Validation Model (HelloWorld) | ✅ Complete |
| 5 | Integrity Guard System | ✅ Complete |
| 6 | Execution Workflow | ✅ Complete |
| 7 | Logging & Finalization | ✅ Complete |
| 8 | TankerTransfer V1 (3-scenario model) | ✅ Complete |
| 9 | TankerTransfer V2 (realistic physics rebuild) | ✅ Complete |
| 10 | Interactive Web Dashboard (Streamlit + Plotly) | ✅ Complete |
| 11 | Parametric Sweeps A–D (single-variable, 200 sims) | ✅ Complete |
| 12 | Parametric Sweeps E–G (multi-dimensional, 250 sims) | ✅ Complete |
| 13 | Mega 5D Sweep H (1,080 sims, 125 min runtime) | ✅ Complete |
| 14 | Master Excel Report (9 sheets, 1,530 rows) | ✅ Complete |
| 15 | Dashboard Enhancements (logo, pressurization calc) | ✅ Complete |

### Summary of Completed Work

- **1,530 total simulations** across 8 parametric sweeps — zero failures
- **ANOVA analysis** identifying top 5 variables: viscosity (32%), compressor (30%), hose (20%), volume (4%), pressure (0.2%)
- **Key finding:** Pre-pressurizing the tank is counterproductive — 0 psig always wins
- **3 recommended upgrade solutions** with cost-benefit analysis
- **Extreme case analysis:** 9.4 min (dream) to 108.1 min (nightmare) — 11.5× range
- **Interactive dashboard** with live pressurization time calculator
- **Master Excel report** downloadable with all sweep data
