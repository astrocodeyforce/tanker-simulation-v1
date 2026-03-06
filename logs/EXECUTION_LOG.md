# EXECUTION LOG

## Run History

All simulation runs and integrity checks are logged here.

---

### Run Template

```
## Run #X — YYYY-MM-DD HH:MM UTC

### Pipeline Steps
| Step | Command | Result | Duration |
|------|---------|--------|----------|
| 1 | guard_check.sh --snapshot | ✅/❌ | Xs |
| 2 | docker compose run openmodelica | ✅/❌ | Xs |
| 3 | docker compose run python-viz | ✅/❌ | Xs |
| 4 | guard_check.sh --verify | ✅/❌ | Xs |

### Outputs Generated
- [ ] outputs/HelloWorld_res.csv
- [ ] outputs/HelloWorld_plot.png

### Integrity Check
- Containers: PASS/FAIL
- Networks: PASS/FAIL
- Volumes: PASS/FAIL

### Anomalies
None / <describe>
```

---

*No runs executed yet. First run will be recorded here after environment validation.*

---

## App Run — 2026-02-20 19:53:42 UTC

**Overall: SUCCESS**

### Scenarios
- ✅ scenario_A_pressurize_only
- ✅ scenario_B_split_air
- ✅ scenario_C_pump_only

### Guard Check: PASS

### Run Directories
- data/runs/20260220_195342_scenario_A_pressurize_only/
- data/runs/20260220_195402_scenario_B_split_air/
- data/runs/20260220_195422_scenario_C_pump_only/

### Completed: 2026-02-20 19:54:51 UTC

---

## Tier 1+2 Implementation — 2026-03-06

**Overall: SUCCESS**

### Tier 1A — K-Fittings (3-Segment Piping)
- Changed piping from 1 segment (L=20ft, K=2.5) to 3 segments (1+20+1 ft, K=0.5+0.5+2.1)
- ✅ All 5 baseline products re-ran successfully

### Tier 1B — Uncertainty Study (RSS per White Eq. E.1)
- 45 simulations (3 products × 7 params × 2 directions + 3 base cases)
- ✅ All 45 simulations completed — zero failures
- Results: `data/uncertainty_results_20260306_171656.json`

### Tier 2A — Non-Newtonian Rheology
- Added power-law model (n_power_law parameter, mu_eff per segment)
- ✅ Backward compatibility: n=1.0 → 0.000% difference
- ✅ Non-Newtonian test (NIPOL latex n=0.4): 7% faster (shear-thinning)

### Tier 2B — Two-Phase End-of-Unload
- Added f_two_phase cubic smoothstep (h_liquid < D_outlet)
- ✅ Verified onset at t=47.0 min, completion near h=0.14"
- Only affects last ~90 gal of 6,500 gal load

### Final Comparison (5 Products)
| Product | Before | After | Δ |
|---------|--------|-------|---|
| OCD (0.6 cP) | 47.0 min | 47.6 min | +1.2% |
| Ethylene Glycol (16.1 cP) | 48.0 min | 48.6 min | +1.3% |
| Resin Solution (500 cP) | 57.2 min | 58.5 min | +2.4% |
| Tall Oil Rosin (5000 cP) | 110.1 min | 114.5 min | +4.0% |
| Perchloroethylene (9900 cP) | 163.2 min | 179.1 min | +9.7% |

### Git Commits
- `e777681` — v2.1 physics (Tier 1+2)
- `6dd8754` — Dashboard updates

### Dashboard Restart
- Container restarted, HTTP 200 verified on http://31.220.52.220:8501/

### Completed: 2026-03-06 ~18:30 UTC
