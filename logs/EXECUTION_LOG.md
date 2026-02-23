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
