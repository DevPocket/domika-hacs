#!/usr/bin/env bash
#
# check-bash.sh — check shell scripts with shfmt (layout, .editorconfig) and shellcheck (.shellcheckrc).
#
# Usage (from anywhere; defaults to every *.sh under scripts/):
#   scripts/check-bash.sh           # report only; exit 1 if anything is off
#   scripts/check-bash.sh --fix     # reformat in place, then lint
#   scripts/check-bash.sh PATH ...  # restrict to the given files
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

FIX=0
FILES=()
for arg in "$@"; do
  case "$arg" in
    --fix) FIX=1 ;;
    -h | --help)
      sed -n '2,9p' "$0"
      exit 0
      ;;
    *) FILES+=("$arg") ;;
  esac
done

if [[ ${#FILES[@]} -eq 0 ]]; then
  while IFS= read -r f; do FILES+=("$f"); done < <(find "$ROOT/scripts" -type f -name '*.sh' | sort)
fi

for tool in shfmt shellcheck; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "❌ $tool not found (brew install $tool)" >&2
    exit 2
  fi
done

RC=0
if [[ "$FIX" = 1 ]]; then
  shfmt -w "${FILES[@]}"
elif ! shfmt -d "${FILES[@]}"; then
  RC=1
fi
if ! shellcheck -x -f gcc "${FILES[@]}"; then
  RC=1
fi

if [[ "$RC" -eq 0 ]]; then
  echo "✅ ${#FILES[@]} script(s) clean"
else
  echo "❌ shell check failed" >&2
fi
exit "$RC"
