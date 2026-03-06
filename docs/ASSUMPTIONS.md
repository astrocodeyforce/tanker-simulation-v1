# ASSUMPTIONS

## Environment Assumptions

| # | Assumption | Verified |
|---|-----------|----------|
| 1 | VPS runs Ubuntu 24.04.3 LTS | ✅ Confirmed |
| 2 | Docker Engine 28.5.1 is installed and running | ✅ Confirmed |
| 3 | Docker Compose v2.40.2 is available as plugin | ✅ Confirmed |
| 4 | User has root access | ✅ Confirmed (running as root) |
| 5 | Sufficient disk space (163G free) | ✅ Confirmed |
| 6 | Sufficient RAM (10Gi free of 15Gi) | ✅ Confirmed |
| 7 | Internet access available for pulling Docker images | ⬜ Assumed |

## Production Container Assumptions

| # | Assumption | Verified |
|---|-----------|----------|
| 1 | 4 production containers exist and must not be disturbed | ✅ Confirmed |
| 2 | hmdm + hmdm-db use network `headwind-mdm_hmdm_internal` | ✅ Confirmed |
| 3 | n8n + traefik use network `root_default` | ✅ Confirmed |
| 4 | Ports 80, 443, 5678, 8080, 31000 are in use | ✅ Confirmed |
| 5 | 4 named volumes exist: hmdm_pgdata, hmdm_work, n8n_data, traefik_data | ✅ Confirmed |

## Project Assumptions

| # | Assumption | Rationale |
|---|-----------|-----------|
| 1 | OpenModelica Docker image is publicly available | Official image on Docker Hub |
| 2 | Python 3.12-slim image is publicly available | Official image on Docker Hub |
| 3 | No GUI is needed — headless execution only | VPS has no display server |
| 4 | Simulation output is CSV format | Standard OpenModelica output |
| 5 | `/opt/sim-lab/` is a safe location for project files | Not used by any system service or existing container |
| 6 | Bind mounts are preferred over named volumes | Easier to manage, no risk of collision with production volumes |

## Risk Assumptions

| # | Assumption | Mitigation |
|---|-----------|------------|
| 1 | Docker image pulls won't affect running containers | Docker architecture guarantees this |
| 2 | Creating a new bridge network won't affect existing networks | Docker isolates networks by name |
| 3 | Bind mounts under /opt/sim-lab/ won't collide with anything | Directory did not exist before this project |
| 4 | Resource usage of sim containers won't starve production | Models are small; containers are short-lived (run, not up) |

## Physics Model Assumptions (v2.1)

| # | Assumption | Impact | Status |
|---|-----------|--------|--------|
| 1 | All products are Newtonian unless n_power_law is explicitly set | n defaults to 1.0; no behavior change for existing configs | ✅ Verified (0.000% diff) |
| 2 | Power-law applies to all pipe segments independently | μ_eff varies per segment based on local velocity | ✅ Implemented |
| 3 | Shear rate floored at 0.01 s⁻¹ | Prevents μ_eff → ∞ at zero flow (n < 1) | ✅ Numerical safeguard |
| 4 | Two-phase onset at h_liquid < D_outlet | Cubic smoothstep gives smooth transition | ✅ Verified |
| 5 | Two-phase only affects last ~1.4% of load | 90 gal of 6,500 gal; minimal impact on total time | ✅ Verified |
| 6 | Standard hose length is 20 ft | Per Bull & Bear fleet standard | ✅ Confirmed by user |
| 7 | Standard piping is 3 segments | Nozzle (1ft) + hose (20ft) + customer connection (1ft) | ✅ Confirmed by user |
| 8 | Uncertainty perturbations are independent | RSS combination per White Eq. E.1 is valid | ✅ Textbook-verified |
