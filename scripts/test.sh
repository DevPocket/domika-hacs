#!/usr/bin/env bash
#
# test.sh — run the integration's unit tests and print a short summary.
#
# Usage (from anywhere):
#   scripts/test.sh                 # all tests
#   scripts/test.sh -k storage      # any pytest arguments are passed through
#   scripts/test.sh --full          # also print the whole pytest output
#
# Creates .venv (Python 3.14, or $PYTHON) and installs requirements_test.txt when either is missing or changed.
# The full output of every run is kept in .test-logs/last.log.
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
REQUIREMENTS="$ROOT/requirements_test.txt"
STAMP="$VENV/.requirements_test.sha"
LOG_DIR="$ROOT/.test-logs"
LOG="$LOG_DIR/last.log"
PYTHON_BIN="${PYTHON:-python3.14}"

if [[ -t 1 ]]; then
  BOLD=$'\033[1m'
  RED=$'\033[0;31m'
  GRN=$'\033[0;32m'
  DIM=$'\033[0;90m'
  RST=$'\033[0m'
else
  BOLD=""
  RED=""
  GRN=""
  DIM=""
  RST=""
fi

FULL=0
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --full) FULL=1 ;;
    -h | --help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) ARGS+=("$arg") ;;
  esac
done

python_version() {
  "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null
}

prepare_venv() {
  local expected
  expected="$(python_version "$PYTHON_BIN")"
  if [[ -z "$expected" ]]; then
    printf '%s❌ %s not found (set PYTHON to override)%s\n' "$RED" "$PYTHON_BIN" "$RST" >&2
    return 1
  fi
  if [[ "$(python_version "$VENV/bin/python")" != "$expected" ]]; then
    printf '%s▸ creating .venv with %s%s\n' "$DIM" "$PYTHON_BIN" "$RST"
    rm -rf "$VENV"
    "$PYTHON_BIN" -m venv "$VENV" || return 1
  fi
  local wanted
  wanted="$(shasum "$REQUIREMENTS" | cut -d' ' -f1)"
  if [[ "$(cat "$STAMP" 2>/dev/null)" != "$wanted" ]]; then
    printf '%s▸ installing requirements_test.txt%s\n' "$DIM" "$RST"
    "$VENV/bin/python" -m pip install -q --disable-pip-version-check -r "$REQUIREMENTS" || return 1
    printf '%s\n' "$wanted" >"$STAMP"
  fi
}

if ! prepare_venv; then
  printf '%s❌ could not prepare .venv%s\n' "$RED" "$RST" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"
cd "$ROOT" || exit 2
COLUMNS=300 "$VENV/bin/python" -m pytest -q --no-header -p no:cacheprovider --tb=short -rfE ${ARGS[@]+"${ARGS[@]}"} >"$LOG" 2>&1
RC=$?

if [[ "$FULL" = 1 ]]; then
  cat "$LOG"
  echo
fi

# One line per failure: the test id and pytest's short reason (COLUMNS keeps it from being cut).
grep -E '^(FAILED|ERROR) ' "$LOG" | while IFS= read -r line; do
  printf '%s✗ %s%s\n' "$RED" "${line#* }" "$RST"
done

SUMMARY="$(grep -E '^[=]* ?[0-9]+ (passed|failed|error|errors|skipped|deselected)|^no tests ran' "$LOG" | tail -1 | tr -d '=')"
SUMMARY="${SUMMARY# }"
SUMMARY="${SUMMARY% }"
if [[ "$RC" -eq 0 ]]; then
  printf '%s✅ %s%s\n' "$GRN" "${SUMMARY:-tests passed}" "$RST"
else
  printf '%s❌ %s%s\n' "$RED$BOLD" "${SUMMARY:-pytest exited with $RC}" "$RST"
  printf '%sfull log: %s%s\n' "$DIM" "${LOG#"$ROOT"/}" "$RST"
fi
exit "$RC"
