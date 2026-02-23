# RISK AND ISOLATION

## Identified Risks

| # | Risk | Severity | Likelihood | Impact |
|---|------|----------|-----------|--------|
| 1 | **Container name collisions** | HIGH | LOW | Could stop/replace production containers |
| 2 | **Network collisions** | HIGH | LOW | Could disrupt inter-container communication |
| 3 | **Volume collisions** | CRITICAL | LOW | Could corrupt or destroy production data |
| 4 | **Port conflicts** | HIGH | MEDIUM | Could prevent Traefik/n8n/HMDM from binding |
| 5 | **Resource starvation** | MEDIUM | LOW | Could degrade production performance |
| 6 | **Accidental system-wide Docker commands** | CRITICAL | MEDIUM | Could destroy all containers/volumes/networks |
| 7 | **Image pull failures** | LOW | LOW | Simulation won't start, but no production impact |

---

## Isolation Strategy

### 1. COMPOSE_PROJECT_NAME Isolation

```
COMPOSE_PROJECT_NAME=simlab
```

- All containers will be prefixed: `simlab-openmodelica-1`, `simlab-python-viz-1`
- Cannot collide with `hmdm`, `hmdm-db`, `root-n8n-1`, `root-traefik-1`
- Docker Compose operations (up, down, restart) affect only `simlab` project

### 2. Dedicated Docker Network

```yaml
networks:
  simlab_network:
    driver: bridge
    # NO 'external: true' — this is project-only
```

- Creates `simlab_simlab_network` — unique name, no collision risk
- Production networks: `headwind-mdm_hmdm_internal`, `root_default` — completely separate
- No external network references

### 3. Zero Published Ports

```yaml
# NO 'ports:' directive in any service
```

- Occupied ports: 80, 443 (Traefik), 5678 (n8n), 8080, 31000 (HMDM)
- Our containers publish NOTHING — zero port conflict risk
- All communication is internal via `simlab_network` or filesystem (bind mounts)

### 4. Project-Only Bind Mounts

```yaml
volumes:
  - ./models:/work/models      # /opt/sim-lab/truck-tanker-sim-env/models
  - ./outputs:/work/outputs    # /opt/sim-lab/truck-tanker-sim-env/outputs
```

- NO named Docker volumes (avoids collision with `hmdm_pgdata`, `n8n_data`, etc.)
- All mounts are relative to project directory
- Production volumes are untouched

### 5. Guard State Verification

```
Before run:  snapshot containers, networks, volumes → _guard/*_before.txt
After run:   snapshot containers, networks, volumes → _guard/*_after.txt
Compare:     diff before vs after (excluding simlab-prefixed items)
```

- Any unexpected change = FAIL
- New images are allowed (expected: pulling openmodelica, python images)

---

## Forbidden Operations

These commands must **NEVER** be executed on this VPS during this project:

| Command | Risk |
|---------|------|
| `docker system prune` | Removes all stopped containers, unused networks, dangling images |
| `docker network prune` | Removes all unused networks — could delete production networks if containers are temporarily stopped |
| `docker volume prune` | **DESTROYS** all unused volumes — could wipe production databases |
| `docker compose down` (outside project dir) | Could stop production containers |
| `docker rm -f $(docker ps -aq)` | Kills ALL containers including production |
| `docker stop $(docker ps -q)` | Stops ALL running containers |

### Safe Alternatives

| Need | Safe Command |
|------|-------------|
| Clean up sim-lab only | `cd /opt/sim-lab/truck-tanker-sim-env && docker compose down` |
| Remove sim-lab images | `docker rmi <specific-image-id>` |
| Remove sim-lab network | `docker network rm simlab_simlab_network` |
| View project containers | `docker compose -p simlab ps` |

---

## Existing Production State (Reference)

### Containers
| Name | Image | Status |
|------|-------|--------|
| hmdm | headwindmdm/hmdm:latest | Up |
| hmdm-db | postgres:15-alpine | Up (healthy) |
| root-n8n-1 | docker.n8n.io/n8nio/n8n | Up |
| root-traefik-1 | traefik | Up |

### Networks
| Name | Driver |
|------|--------|
| bridge | bridge |
| headwind-mdm_hmdm_internal | bridge |
| host | host |
| none | null |
| root_default | bridge |

### Volumes
| Name |
|------|
| headwind-mdm_hmdm_pgdata |
| headwind-mdm_hmdm_work |
| n8n_data |
| traefik_data |

---

## Port Exposure Strategy

### Dashboard Port Binding

The interactive visualization dashboard is the **only** service that publishes a port.
It MUST use **localhost-only** binding:

```yaml
ports:
  - "127.0.0.1:8501:8501"
```

### What This Means

| Binding | Accessible From | Security |
|---------|----------------|----------|
| `127.0.0.1:8501:8501` | **VPS localhost only** | Safe — requires SSH tunnel |
| `0.0.0.0:8501:8501` ❌ | **Entire internet** | DANGEROUS — exposes app publicly |
| `8501:8501` ❌ | **Entire internet** | DANGEROUS — Docker defaults to 0.0.0.0 |

### Why Localhost-Only?

1. **No firewall changes needed** — port 8501 is never exposed to the public network
2. **SSH tunnel required** — only authenticated users can reach the dashboard
3. **No conflict with Traefik** — Traefik binds ports 80/443; 8501 is separate
4. **Principle of least privilege** — the dashboard has no reason to be publicly reachable

### Explicitly Forbidden

| Configuration | Risk |
|--------------|------|
| `ports: ["8501:8501"]` | Binds to 0.0.0.0 — publicly accessible |
| `ports: ["0.0.0.0:8501:8501"]` | Explicitly public — anyone can access |
| `network_mode: host` | Bypasses Docker networking — shares all host ports |
| `--net=host` | Same as above when using `docker run` |
