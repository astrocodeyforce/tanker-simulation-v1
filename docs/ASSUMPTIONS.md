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
