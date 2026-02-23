#!/bin/bash
###############################################################################
# guard_check.sh — Docker State Integrity Verification
#
# PURPOSE:
#   Ensures that running the sim-lab project does NOT affect any existing
#   production Docker containers, networks, or volumes.
#
# USAGE:
#   ./scripts/guard_check.sh --snapshot    Capture baseline state (before run)
#   ./scripts/guard_check.sh --verify      Compare current state to baseline
#
# LOGIC:
#   --snapshot:
#     Saves sorted lists of containers, networks, volumes to _guard/*_before.txt
#
#   --verify:
#     1. Captures current state to _guard/*_after.txt
#     2. Filters OUT any items prefixed with "simlab" (our project)
#     3. Compares filtered before vs filtered after
#     4. If any non-simlab item changed → FAIL
#     5. New images are ALLOWED (we expect to pull openmodelica/python)
#
# EXIT CODES:
#   0 = All checks passed
#   1 = Integrity violation detected
#   2 = Usage error (missing baseline, bad arguments)
###############################################################################

set -euo pipefail

# ---- Configuration ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
GUARD_DIR="${PROJECT_DIR}/_guard"

# Project prefix — containers/networks with this prefix are ours
PROJECT_PREFIX="simlab"

# ---- Helper Functions ----

timestamp() {
    date -u '+%Y-%m-%d %H:%M:%S UTC'
}

log_info() {
    echo "[$(timestamp)] ℹ️  $1"
}

log_pass() {
    echo "[$(timestamp)] ✅ PASS: $1"
}

log_fail() {
    echo "[$(timestamp)] ❌ FAIL: $1"
}

log_error() {
    echo "[$(timestamp)] ❌ ERROR: $1" >&2
}

# Capture current Docker state to files
capture_state() {
    local suffix="$1"  # "before" or "after"

    # Containers: name, image, status (sorted)
    docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' | sort \
        > "${GUARD_DIR}/containers_${suffix}.txt"

    # Networks: name, driver (sorted)
    docker network ls --format '{{.Name}} {{.Driver}}' | sort \
        > "${GUARD_DIR}/networks_${suffix}.txt"

    # Volumes: name only (sorted)
    docker volume ls --format '{{.Name}}' | sort \
        > "${GUARD_DIR}/volumes_${suffix}.txt"

    # Images: repo:tag, ID (sorted) — for reference, not strict checking
    docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | sort \
        > "${GUARD_DIR}/images_${suffix}.txt"
}

# Filter out lines starting with or containing the project prefix
filter_project_items() {
    local file="$1"
    # Remove lines where the first field (name) starts with the project prefix
    grep -v "^${PROJECT_PREFIX}" "$file" | grep -v "^${PROJECT_PREFIX}_" || true
}

# Compare two state files, ignoring project-prefixed items
compare_states() {
    local resource_type="$1"
    local before_file="${GUARD_DIR}/${resource_type}_before.txt"
    local after_file="${GUARD_DIR}/${resource_type}_after.txt"
    local before_filtered after_filtered

    if [ ! -f "$before_file" ]; then
        log_error "Baseline file missing: $before_file"
        log_error "Run './scripts/guard_check.sh --snapshot' first"
        return 2
    fi

    if [ ! -f "$after_file" ]; then
        log_error "After-state file missing: $after_file"
        return 2
    fi

    # Filter out project items from both files
    before_filtered=$(filter_project_items "$before_file")
    after_filtered=$(filter_project_items "$after_file")

    # Compare filtered lists
    if [ "$before_filtered" = "$after_filtered" ]; then
        log_pass "${resource_type}: No non-project changes detected"
        return 0
    else
        log_fail "${resource_type}: Unexpected changes detected!"
        echo ""
        echo "  --- Before (non-project items) ---"
        echo "$before_filtered" | sed 's/^/  /'
        echo ""
        echo "  --- After (non-project items) ---"
        echo "$after_filtered" | sed 's/^/  /'
        echo ""
        echo "  --- Diff ---"
        diff <(echo "$before_filtered") <(echo "$after_filtered") | sed 's/^/  /' || true
        echo ""
        return 1
    fi
}

# ---- Main Logic ----

usage() {
    echo "Usage: $0 [--snapshot | --verify]"
    echo ""
    echo "  --snapshot   Capture baseline Docker state (run BEFORE operations)"
    echo "  --verify     Verify Docker state matches baseline (run AFTER operations)"
    exit 2
}

if [ $# -ne 1 ]; then
    usage
fi

mkdir -p "$GUARD_DIR"

case "$1" in
    --snapshot)
        echo "============================================"
        echo " Guard: Capturing Baseline Snapshot"
        echo " Time:  $(timestamp)"
        echo "============================================"
        echo ""

        capture_state "before"

        log_info "Containers: $(wc -l < "${GUARD_DIR}/containers_before.txt") found"
        log_info "Networks:   $(wc -l < "${GUARD_DIR}/networks_before.txt") found"
        log_info "Volumes:    $(wc -l < "${GUARD_DIR}/volumes_before.txt") found"
        log_info "Images:     $(wc -l < "${GUARD_DIR}/images_before.txt") found"

        echo ""
        log_pass "Baseline snapshot saved to ${GUARD_DIR}/"
        echo ""
        ;;

    --verify)
        echo "============================================"
        echo " Guard: Integrity Verification"
        echo " Time:  $(timestamp)"
        echo "============================================"
        echo ""

        # Check baseline exists
        for f in containers_before.txt networks_before.txt volumes_before.txt; do
            if [ ! -f "${GUARD_DIR}/$f" ]; then
                log_error "Baseline missing: ${GUARD_DIR}/$f"
                log_error "Run './scripts/guard_check.sh --snapshot' first"
                exit 2
            fi
        done

        # Capture current state
        log_info "Capturing current Docker state..."
        capture_state "after"

        # Compare each resource type
        FAILURES=0

        echo ""
        echo "--- Checking Containers ---"
        compare_states "containers" || FAILURES=$((FAILURES + 1))

        echo ""
        echo "--- Checking Networks ---"
        compare_states "networks" || FAILURES=$((FAILURES + 1))

        echo ""
        echo "--- Checking Volumes ---"
        compare_states "volumes" || FAILURES=$((FAILURES + 1))

        # Images: informational only (new images are expected)
        echo ""
        echo "--- Checking Images (informational — new images allowed) ---"
        BEFORE_IMAGES=$(wc -l < "${GUARD_DIR}/images_before.txt")
        AFTER_IMAGES=$(wc -l < "${GUARD_DIR}/images_after.txt")
        if [ "$AFTER_IMAGES" -ge "$BEFORE_IMAGES" ]; then
            log_pass "Images: ${BEFORE_IMAGES} before → ${AFTER_IMAGES} after (new images OK)"
        else
            log_info "Images: ${BEFORE_IMAGES} before → ${AFTER_IMAGES} after (some removed — verify manually)"
        fi

        # Final verdict
        echo ""
        echo "============================================"
        if [ "$FAILURES" -eq 0 ]; then
            log_pass "ALL INTEGRITY CHECKS PASSED"
            echo " No production containers, networks, or volumes were affected."
            echo "============================================"
            exit 0
        else
            log_fail "${FAILURES} INTEGRITY CHECK(S) FAILED"
            echo " ⚠️  Production Docker state may have been modified!"
            echo " Review the diff output above and investigate."
            echo "============================================"
            exit 1
        fi
        ;;

    *)
        usage
        ;;
esac
