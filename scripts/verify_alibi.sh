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

tmux_send_ctrl_c() {
  local conf=( )
  if [[ -f /exec-daemon/tmux.portal.conf ]]; then
    conf=(-f /exec-daemon/tmux.portal.conf)
  fi
  tmux "${conf[@]}" send-keys -t "$1:0.0" C-c
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

gate "2 Vane Hall assets"
ASSET_MISS=0
for f in \
  frontend/public/portraits/vane_hall/margaret_neutral.webp \
  frontend/public/portraits/vane_hall/crane_neutral.webp \
  frontend/public/portraits/vane_hall/pell_neutral.webp \
  frontend/public/portraits/vane_hall/ada_neutral.webp \
  frontend/public/backdrops/landscape_16x9/library.webp \
  frontend/public/backdrops/landscape_16x9/manor_exterior.webp \
  frontend/public/backdrops/mobile_9x16/library.webp \
  frontend/public/backdrops/ultrawide_21x9/library.webp \
  frontend/public/backdrops/scene_originals/library.webp \
  frontend/public/art/vane_hall/victim.webp \
  frontend/public/evidence/vane_hall/decanter.webp \
  frontend/public/evidence/vane_hall/solicitor_letter.webp \
  frontend/public/evidence/vane_hall/ledger.webp \
  frontend/public/evidence/vane_hall/cyanide_jar.webp \
  frontend/public/evidence/vane_hall/cigar_ash.webp \
  frontend/public/evidence/vane_hall/cigar_case.webp \
  frontend/public/evidence/vane_hall/necklace_clasp.webp \
  frontend/public/evidence/vane_hall/torn_reference.webp \
  frontend/public/evidence/vane_hall/ashes_in_grate.webp
do
  if [[ ! -f "$ROOT/$f" ]]; then
    fail "missing $f"
    ASSET_MISS=1
  fi
done
if [[ "$ASSET_MISS" -eq 0 ]]; then
  pass "Vane Hall portraits + backdrop + victim + evidence webps present"
fi

gate "3 unit tests"
if (
  cd "$ROOT/backend"
  LLM_MODE=scripted "$PY" -m pytest -q -m "not integration"
) >"$OUT/pytest.log" 2>&1; then
  pass "backend pytest (log $OUT/pytest.log)"
else
  fail "backend pytest (log $OUT/pytest.log)"
  tail -20 "$OUT/pytest.log" || true
fi
if (cd "$ROOT/frontend" && npx vitest run src/sensors/faceLandmarker.test.ts src/lib/paintedPortrait.test.ts src/lib/backdrops.test.ts) \
    >"$OUT/vitest-sensors-assets.log" 2>&1; then
  pass "frontend sensor/asset vitest (log $OUT/vitest-sensors-assets.log)"
else
  fail "frontend sensor/asset vitest (log $OUT/vitest-sensors-assets.log)"
  tail -30 "$OUT/vitest-sensors-assets.log" || true
fi

# A backend this script starts keeps its games in $OUT, out of the player's Archive (backend/alibi.db).
BACKEND_CMD="set -a && . ./.env && set +a && export LLM_MODE=scripted DATABASE_URL='sqlite+aiosqlite:///$OUT/verify.db' && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 >>'$OUT/backend.log' 2>&1"

gate "4 servers"
if [[ "$SKIP_START" -eq 0 ]]; then
  if ! curl -fsS "$API/api/health" >/dev/null 2>&1; then
    rm -f "$OUT/verify.db" "$OUT/backend.log"
    tmux_run "$BACKEND_SESSION" "$ROOT/backend" "$BACKEND_CMD"
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

gate "5 API playtest"
rm -f "$OUT/game_id"
if LLM_MODE=scripted PLAYTEST_GAME_FILE="$OUT/game_id" "$PY" "$ROOT/scripts/api_playtest.py" "$API" \
    >"$OUT/api-playtest.log" 2>&1; then
  pass "api playtest (log $OUT/api-playtest.log)"
else
  fail "api playtest (log $OUT/api-playtest.log)"
  tail -30 "$OUT/api-playtest.log" || true
fi

gate "6 restart persistence"
if [[ "$STARTED_BACKEND" -eq 1 && -s "$OUT/game_id" ]]; then
  gid="$(cat "$OUT/game_id")"
  curl -fsS "$API/api/games/$gid" >"$OUT/game-before-restart.json" || true
  tmux_send_ctrl_c "$BACKEND_SESSION"
  for ((i = 1; i <= 20; i++)); do
    curl -fsS "$API/api/health" >/dev/null 2>&1 || break
    sleep 0.5
  done
  tmux_run "$BACKEND_SESSION" "$ROOT/backend" "$BACKEND_CMD"
  if wait_http "$API/api/health" "restarted backend"; then
    curl -fsS "$API/api/games/$gid" >"$OUT/game-after-restart.json" || true
    if "$PY" -c 'import json, sys; a, b = (json.load(open(p)) for p in sys.argv[1:]); sys.exit(a != b)' \
        "$OUT/game-before-restart.json" "$OUT/game-after-restart.json" 2>/dev/null; then
      pass "GET /api/games/$gid is identical after a backend restart"
    else
      fail "game state changed across restart (diff $OUT/game-before-restart.json $OUT/game-after-restart.json)"
    fi
  fi
else
  echo "SKIP  restart gate needs a backend this script started (run without --skip-start, servers down)"
fi

if [[ "$QUICK" -eq 0 ]]; then
  gate "7 redteam"
  if (
    cd "$ROOT"
    LLM_MODE=scripted "$PY" scripts/redteam.py --case backend/app/cases/vane_hall.json
  ) >"$OUT/redteam.log" 2>&1; then
    if grep -Eq '(^|[^0-9])0 FAIL([^0-9]|$)' "$OUT/redteam.log"; then
      pass "redteam (log $OUT/redteam.log)"
    else
      fail "redteam reported failures (log $OUT/redteam.log)"
    fi
  else
    fail "redteam exited non-zero (log $OUT/redteam.log)"
    tail -20 "$OUT/redteam.log" || true
  fi

  gate "8 frontend test + build"
  if (cd "$ROOT/frontend" && npm test) >"$OUT/vitest.log" 2>&1; then
    pass "vitest full (log $OUT/vitest.log)"
  else
    fail "vitest full (log $OUT/vitest.log)"
  fi
  if (cd "$ROOT/frontend" && npm run build) >"$OUT/frontend-build.log" 2>&1; then
    pass "frontend build (log $OUT/frontend-build.log)"
  else
    fail "frontend build (log $OUT/frontend-build.log)"
  fi
fi

echo
echo "Harness gaps (not checked here): WS updates painted in the browser, live Gemini, case Author,"
echo "live webcam (manual — see verify-alibi skill), immersive low-text UX. See docs/BROKEN.md."
echo "API playtest may print a GAP line without failing."
echo


if [[ "$FAILS" -eq 0 ]]; then
  echo "VERIFY ALIBI: ALL GATES PASSED"
  exit 0
fi
echo "VERIFY ALIBI: $FAILS GATE(S) FAILED"
exit 1
