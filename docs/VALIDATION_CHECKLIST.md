# VALIDATION CHECKLIST

## Environment Setup Acceptance Criteria

Each item must pass before the environment is considered ready.

---

### Phase 2 — Baseline Snapshot

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Docker baseline snapshot captured | 🔲 | `_guard/containers_before.txt` exists |
| 2 | Networks baseline captured | 🔲 | `_guard/networks_before.txt` exists |
| 3 | Volumes baseline captured | 🔲 | `_guard/volumes_before.txt` exists |
| 4 | Images baseline captured | 🔲 | `_guard/images_before.txt` exists |

### Phase 3 — Docker Environment

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 5 | docker-compose.yml created | 🔲 | File exists, valid YAML |
| 6 | COMPOSE_PROJECT_NAME = simlab | 🔲 | `.env` file contains it |
| 7 | No ports published | 🔲 | No `ports:` in compose file |
| 8 | Dedicated network defined | 🔲 | `simlab_network` in compose |
| 9 | No external networks | 🔲 | No `external: true` in compose |
| 10 | Bind mounts only (no named volumes) | 🔲 | Volume definitions use `./<path>` |

### Phase 4 — Validation Model

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 11 | HelloWorld.mo model exists | 🔲 | `models/HelloWorld.mo` |
| 12 | Simulation script exists | 🔲 | `scripts/run_simulation.sh` |
| 13 | Python viz script exists | 🔲 | `scripts/plot_results.py` |
| 14 | HelloWorld simulation executed | 🔲 | `outputs/HelloWorld_res.csv` exists |
| 15 | Visualization PNG generated | 🔲 | `outputs/HelloWorld_plot.png` exists |

### Phase 5 — Integrity Verification

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 16 | Guard script exists | 🔲 | `scripts/guard_check.sh` |
| 17 | Containers unchanged after run | 🔲 | Guard check passes |
| 18 | Networks unchanged after run | 🔲 | Guard check passes |
| 19 | Volumes unchanged after run | 🔲 | Guard check passes |

### Phase 6 — Execution Workflow

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 20 | Full pipeline runs end-to-end | 🔲 | `scripts/run_all.sh` completes |
| 21 | Results logged to EXECUTION_LOG.md | 🔲 | Log entry exists with timestamp |

---

## Sign-Off

| Role | Approved | Date |
|------|----------|------|
| Engineer | 🔲 | — |
| Reviewer | 🔲 | — |
