#!/usr/bin/env bash
# Verify Murder Mystery Mayhem boots and the scripted Vane Hall loop works.
# See .cursor/skills/verify-alibi/SKILL.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_START=0
QUICK=0
KEEP_SERVERS=0
for arg in "$@"; do
  case "$arg" in
    --skip-start) SKIP_START=1 ;;
    --quick) QUICK=1 ;;
    --keep-servers) KEEP_SERVERS=1 ;;
    -h|--help)
      echo "Usage: ./scripts/verify_alibi.sh [--skip-start] [--quick] [--keep-servers]"
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 2
      ;;
  esac
done

OUT="${VERIFY_ALIBI_OUT:-$ROOT/.verify-alibi}"
mkdir -p "$OUT"
PY="$ROOT/backend/.venv/bin/python"
API="http://127.0.0.1:8000"
WEB="http://127.0.0.1:5173"
BACKEND_SESSION="verify-alibi-backend"
FRONTEND_SESSION="verify-alibi-frontend"
STARTED_BACKEND=0
STARTED_FRONTEND=0
FAILS=0

pass() { echo "PASS  $*"; }
fail() { echo "FAIL  $*"; FAILS=$((FAILS + 1)); }
gate() { echo; echo "== $* =="; }

cleanup() {
  if [[ "$KEEP_SERVERS" -eq 1 ]]; then
    return
  fi
  if [[ "$STARTED_BACKEND" -eq 1 ]]; then
    tmux -f /exec-daemon/tmux.portal.conf kill-session -t "=$BACKEND_SESSION" 2>/dev/null || true
  fi
  if [[ "$STARTED_FRONTEND" -eq 1 ]]; then
    tmux -f /exec-daemon/tmux.portal.conf kill-session -t "=$FRONTEND_SESSION" 2>/dev/null || true
  fi
}
trap cleanup EXIT

have_cmd() { command -v "$1" >/dev/null 2>&1; }

tmux_run() {
  # tmux_run SESSION CWD COMMAND
  local session="$1" cwd="$2" cmd="$3"
  if ! have_cmd tmux; then
    fail "tmux missing; start servers yourself and re-run with --skip-start"
    exit 2
  fi
  local conf=( )
  if [[ -f /exec-daemon/tmux.portal.conf ]]; then
    conf=(-f /exec-daemon/tmux.portal.conf)
  fi
  tmux "${conf[@]}" has-session -t "=$session" 2>/dev/null || \
    tmux "${conf[@]}" new-session -d -s "$session" -c "$cwd" -- "${SHELL:-bash}" -l
  tmux "${conf[@]}" send-keys -t "$session:0.0" "$cmd" C-m
}

wait_http() {
  local url="$1" name="$2" tries="${3:-40}"
  local i
  for ((i = 1; i <= tries; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  fail "$name did not become ready at $url (see $OUT)"
  return 1
}

gate "1 tooling"
if [[ ! -x "$PY" ]]; then
  fail "backend/.venv missing. Install python3-venv, then: make setup (npm may need --legacy-peer-deps)"
  exit 2
fi
if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  fail "frontend/node_modules missing. From frontend/: npm install --legacy-peer-deps"
  exit 2
fi
pass "venv and node_modules present"

gate "2 unit tests"
if (
  cd "$ROOT/backend"
  LLM_MODE=scripted "$PY" -m pytest -q -m "not integration"
) >"$OUT/pytest.log" 2>&1; then
  pass "pytest (log $OUT/pytest.log)"
else
  fail "pytest (log $OUT/pytest.log)"
  tail -20 "$OUT/pytest.log" || true
fi

gate "3 servers"
if [[ "$SKIP_START" -eq 0 ]]; then
  if ! curl -fsS "$API/api/health" >/dev/null 2>&1; then
    tmux_run "$BACKEND_SESSION" "$ROOT/backend" \
      "set -a && . ./.env && set +a && export LLM_MODE=scripted && .venv/bin/uvicorn --app-dir ../scripts mock_api:app --host 127.0.0.1 --port 8000 >'$OUT/backend.log' 2>&1"
    STARTED_BACKEND=1
  fi
  if ! curl -fsS "$WEB/" >/dev/null 2>&1; then
    tmux_run "$FRONTEND_SESSION" "$ROOT/frontend" \
      "npm run dev -- --host 127.0.0.1 --port 5173 >'$OUT/frontend.log' 2>&1"
    STARTED_FRONTEND=1
  fi
fi

if wait_http "$API/api/health" "backend"; then
  health_json="$(curl -fsS "$API/api/health" | tee "$OUT/health.json")"
  if echo "$health_json" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
    pass "backend health ($health_json)"
  else
    fail "backend health payload ($health_json)"
  fi
fi

if wait_http "$WEB/" "frontend"; then
  code="$(curl -sS -o /dev/null -w '%{http_code}' "$WEB/")"
  if [[ "$code" == "200" ]]; then
    pass "frontend HTTP $code"
  else
    fail "frontend HTTP $code"
  fi
fi

gate "4 API playtest"
if LLM_MODE=scripted "$PY" "$ROOT/scripts/api_playtest.py" "$API" >"$OUT/api-playtest.log" 2>&1; then
  pass "api playtest (log $OUT/api-playtest.log)"
else
  fail "api playtest (log $OUT/api-playtest.log)"
  tail -30 "$OUT/api-playtest.log" || true
fi

if [[ "$QUICK" -eq 0 ]]; then
  gate "5 redteam"
  if (
    cd "$ROOT"
    LLM_MODE=scripted "$PY" scripts/redteam.py --case backend/app/cases/vane_hall.json
  ) >"$OUT/redteam.log" 2>&1; then
    if grep -q "0 FAIL" "$OUT/redteam.log"; then
      pass "redteam (log $OUT/redteam.log)"
    else
      fail "redteam reported failures (log $OUT/redteam.log)"
    fi
  else
    fail "redteam exited non-zero (log $OUT/redteam.log)"
    tail -20 "$OUT/redteam.log" || true
  fi

  gate "6 frontend test + build"
  if (cd "$ROOT/frontend" && npm test) >"$OUT/vitest.log" 2>&1; then
    pass "vitest (log $OUT/vitest.log)"
  else
    fail "vitest (log $OUT/vitest.log)"
  fi
  if (cd "$ROOT/frontend" && npm run build) >"$OUT/frontend-build.log" 2>&1; then
    pass "frontend build (log $OUT/frontend-build.log)"
  else
    fail "frontend build (log $OUT/frontend-build.log)"
  fi
fi

echo
echo "Harness gaps (not checked here): persistence across restart, WebSocket pushes, Watson notebook,"
echo "case generate / api-key routes, Alibi Board / graphs, sensors, cast art. See docs/BROKEN.md."
echo

if [[ "$FAILS" -eq 0 ]]; then
  echo "VERIFY ALIBI: ALL GATES PASSED"
  exit 0
fi
echo "VERIFY ALIBI: $FAILS GATE(S) FAILED"
exit 1
