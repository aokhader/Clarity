#!/usr/bin/env bash
# Answers, one step at a time, the questions a screener asks of Clarity: does it
# lint and typecheck, can only GET requests reach Clio, is any case data in the
# repository, is anything private committed, do the tests pass.
#
#   bash scripts/check.sh
#
# Each step prints ok, FAIL, advisory or SKIPPED. SKIPPED means the step could
# not run and verified nothing: it is not a pass. Exits 1 if any step FAILs.
#
# The no-case-data step derives its forbidden terms from the synced matter:
# scripts/export_raw.py writes every Clio record and page text in data/app.db to
# data/raw-export.json (gitignored), unless KIT_EXPORT names another export.
# PYTHON overrides the interpreter (default: the backend's .venv).

set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)

if [ -x backend/.venv/Scripts/python.exe ]; then DEFAULT_PYTHON=$ROOT/backend/.venv/Scripts/python.exe
else DEFAULT_PYTHON=$ROOT/backend/.venv/bin/python; fi
PYTHON=${PYTHON:-$DEFAULT_PYTHON}
LOG=$(mktemp)
trap 'rm -f "$LOG"' EXIT

failed=0
summary=()

# report <step> <ok|FAIL|advisory|SKIPPED> [detail]
report() {
  local line
  line=$(printf '%-9s %s' "$2" "$1")
  if [ -n "${3:-}" ]; then line="$line ($3)"; fi
  summary+=("$line")
  echo "$line"
  if [ "$2" = FAIL ]; then
    failed=1
    # Show the failing tests and their messages when the log has them, else its end.
    if grep -qE '^\s*not ok|^(FAILED|ERROR) ' "$LOG"; then
      grep -A 8 -E '^\s*not ok|^(FAILED|ERROR) ' "$LOG" | grep -vE '^\s*(---|\.\.\.|duration_ms|type:|location:|failureType:|code:|name:|stack:|operator:|TestContext|Test\.|async Test|--)' | head -n 30
    else
      tail -n 25 "$LOG"
    fi | sed 's/^/          /'
  fi
}

# run <step> <required|advisory> <command...>: ok when the command exits 0.
run() {
  local step=$1 kind=$2 status
  shift 2
  "$@" >"$LOG" 2>&1
  status=$?
  if [ $status -eq 0 ]; then report "$step" ok
  elif [ "$kind" = advisory ]; then report "$step" advisory "exit $status"
  else report "$step" FAIL "exit $status"; fi
}

# node_tests <step> <files...>: Node's test runner. When every test skipped,
# the step is SKIPPED, not ok.
node_tests() {
  local step=$1 status pass skip
  shift
  node --test --test-reporter=tap "$@" >"$LOG" 2>&1
  status=$?
  pass=$(grep -E '^# pass [0-9]+' "$LOG" | tail -n 1 | grep -Eo '[0-9]+$')
  skip=$(grep -E '^# skip(ped)? [0-9]+' "$LOG" | tail -n 1 | grep -Eo '[0-9]+$')
  pass=${pass:-0}
  skip=${skip:-0}
  if [ $status -ne 0 ]; then report "$step" FAIL
  elif [ "$pass" -eq 0 ]; then report "$step" SKIPPED "every test skipped: $(grep -Eo '# SKIP .*' "$LOG" | head -n 1 | sed 's/# SKIP //')"
  elif [ "$skip" -gt 0 ]; then report "$step" ok "$pass passed, $skip skipped"
  else report "$step" ok "$pass passed"; fi
}

# python_tests <step> [pytest args...]: pytest from backend/, same rule for skips.
python_tests() {
  local step=$1 status
  shift
  (cd backend && "$PYTHON" -m pytest -q -rs "$@") >"$LOG" 2>&1
  status=$?
  if [ $status -eq 5 ]; then report "$step" SKIPPED "no tests collected"
  elif [ $status -ne 0 ]; then report "$step" FAIL
  elif grep -Eq '[0-9]+ passed' "$LOG"; then report "$step" ok "$(grep -Eo '[0-9]+ passed' "$LOG" | tail -n 1)"
  else report "$step" SKIPPED "every test skipped"; fi
}

echo "Checks for Clarity at $(git rev-parse --short HEAD 2>/dev/null || echo 'no commit') on $(git branch --show-current 2>/dev/null)"
echo

have_python=1
if ! "$PYTHON" -c 'import pytest' >/dev/null 2>&1; then have_python=0; fi

# 1. Lint
if [ $have_python -eq 0 ]; then report "Lint (ruff)" SKIPPED "no backend venv: see CLAUDE.md, Commands"
else run "Lint (ruff)" required "$PYTHON" -m ruff check backend; fi

# 2. Clio is read-only: only GET can leave the client
if [ $have_python -eq 0 ]; then report "Clio is read-only" SKIPPED "no backend venv"
else python_tests "Clio is read-only" tests/test_clio_client.py; fi

# 3. No case data in code, docs, file names or commit messages
export_file=${KIT_EXPORT:-}
skip_reason="no synced matter in data/app.db and no KIT_EXPORT"
if [ -z "$export_file" ] && [ $have_python -eq 1 ] && [ -f data/app.db ]; then
  "$PYTHON" scripts/export_raw.py >"$LOG" 2>&1
  case $? in
    0) export_file=data/raw-export.json ;;
    # export_raw.py's NOTHING_SYNCED: the invented matter's text is committed on purpose.
    3) skip_reason="data/app.db holds only the synthetic matter from seed-dev; sync a real matter or set KIT_EXPORT" ;;
    *) skip_reason="scripts/export_raw.py failed: $(tail -n 1 "$LOG")" ;;
  esac
fi
if [ -z "$export_file" ] || [ ! -e "$export_file" ]; then
  report "No case data in the repository" SKIPPED "$skip_reason"
else
  KIT_EXPORT="$export_file" node_tests "No case data in the repository" tests/no_literals.test.mjs
fi

# 4. Nothing private is committed
node_tests "Nothing private is committed" tests/repo_hygiene.test.mjs

# 5. Backend tests
if [ $have_python -eq 0 ]; then report "Backend tests" SKIPPED "no backend venv"
else python_tests "Backend tests"; fi

# 6. Frontend types (strict TypeScript)
if [ -d frontend/node_modules ]; then run "Frontend types" required npm --prefix frontend run typecheck
else report "Frontend types" SKIPPED "run npm install in frontend/"; fi

# 7. Any other root Node tests
other_node=$(find tests -name '*.test.mjs' ! -name 'no_literals.test.mjs' ! -name 'repo_hygiene.test.mjs' 2>/dev/null)
if [ -n "$other_node" ]; then node_tests "Other Node tests" $other_node
else report "Other Node tests" SKIPPED "none found"; fi

echo
echo "Summary"
printf '  %s\n' "${summary[@]}"
if [ $failed -eq 0 ]; then
  echo "No step failed. A SKIPPED step verified nothing."
else
  echo "At least one step FAILED."
fi
exit $failed
