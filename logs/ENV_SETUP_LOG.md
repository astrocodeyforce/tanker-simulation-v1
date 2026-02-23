# ENVIRONMENT SETUP LOG

## VPS System Information

| Property | Value |
|----------|-------|
| **OS** | Ubuntu 24.04.3 LTS (Noble Numbat) |
| **Kernel** | Linux (64-bit) |
| **Docker** | 28.5.1 (build e180ab8) |
| **Compose** | v2.40.2 |
| **Disk** | 30G used / 163G free (16% used) |
| **RAM** | 2.9Gi used / 10Gi free / 15Gi total |
| **User** | root |

---

## Initial Docker State Snapshot

**Captured at:** 2026-02-20

### Containers (4 total — all running)

| Container | Image | Status | Ports |
|-----------|-------|--------|-------|
| hmdm | headwindmdm/hmdm:latest | Up 25 hours | 127.0.0.1:8080→8080, 127.0.0.1:31000→31000, 8443 |
| hmdm-db | postgres:15-alpine | Up 25 hours (healthy) | 5432 (internal) |
| root-n8n-1 | docker.n8n.io/n8nio/n8n | Up 14 hours | 127.0.0.1:5678→5678 |
| root-traefik-1 | traefik | Up 2 days | 0.0.0.0:80→80, 0.0.0.0:443→443 |

### Networks (5 total)

| Network | Driver |
|---------|--------|
| bridge | bridge |
| headwind-mdm_hmdm_internal | bridge |
| host | host |
| none | null |
| root_default | bridge |

### Volumes (4 total)

| Volume |
|--------|
| headwind-mdm_hmdm_pgdata |
| headwind-mdm_hmdm_work |
| n8n_data |
| traefik_data |

### Images (6 total)

| Repository | Tag | Image ID |
|-----------|-----|----------|
| postgres | 15-alpine | 15283455b753 |
| headwindmdm/hmdm | latest | f599a4b26b42 |
| docker.n8n.io/n8nio/n8n | latest | 853959bb3055 |
| traefik | latest | 1e55c25c9dc9 |
| traefik | \<none\> | 1fd2908c092e |
| docker.n8n.io/n8nio/n8n | \<none\> | 3f0c599d2f20 |

### Ports in Use

| Port | Service |
|------|---------|
| 22 | sshd |
| 53 | systemd-resolve |
| 80 | docker-proxy (Traefik) |
| 443 | docker-proxy (Traefik) |
| 5678 | docker-proxy (n8n) |
| 8080 | docker-proxy (HMDM) |
| 31000 | docker-proxy (HMDM) |

---

## Setup Actions Performed

| Timestamp | Action | Result |
|-----------|--------|--------|
| 2026-02-20 | Created project directory `/opt/sim-lab/truck-tanker-sim-env/` | ✅ Success |
| 2026-02-20 | Created documentation structure (`docs/`, `logs/`) | ✅ Success |
| 2026-02-20 | Populated all planning documents | ✅ Success |
| 2026-02-20 | Captured baseline Docker state to `_guard/` | ✅ Success |
| 2026-02-20 | Created `docker-compose.yml` with full isolation | ✅ Success |
| 2026-02-20 | Created HelloWorld Modelica model | ✅ Success |
| 2026-02-20 | Created simulation + visualization scripts | ✅ Success |
| 2026-02-20 | Created guard integrity check script | ✅ Success |
