"""TEMPORARY in-memory API (no persistence) so the frontend can be exercised before the real app layer lands.
It runs the real engine Director with the real scripted performer. Delete once backend/app/main.py exists."""
from __future__ import annotations
import asyncio, glob, json, os, pathlib, random, sys, uuid, datetime
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("LLM_MODE", "auto")
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.engine import world as world_mod, public as public_mod, director as director_mod, debrief as debrief_mod
from app.agents import performer as perf_mod, leak_guard, judge

CASES: dict[str, dict] = {}
for f in sorted(glob.glob(str(ROOT / "backend/app/cases/*.json"))):
    try:
        c = json.load(open(f)); CASES[c["id"]] = c
    except Exception as e:  # half-written file from a running agent
        print("skip", f, e)

def preset(setting: str) -> str:
    s = setting.lower()
    if any(k in s for k in ("manor", "hall", "country house")): return "manor"
    if any(k in s for k in ("liner", "ship", "sea", "deck", "rms")): return "liner"
    if any(k in s for k in ("startup", "office", "pitch")): return "startup"
    if any(k in s for k in ("dorm", "campus", "college", "cornell", "ithaca")): return "dorm"
    return "other"

GAMES: dict[str, dict] = {}
app = FastAPI(title="mmm-temp-api")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
scripted = perf_mod.get_scripted_performer()
try:
    live = perf_mod.get_performer()
except Exception as e:
    print("live performer unavailable, using scripted:", e); live = scripted
MODE = getattr(live, "mode", "scripted")
print("performer mode:", MODE)

async def guard(spoken, locked):
    return {"leaked": leak_guard.regex_check(spoken, locked), "reason": "regex"}

def game_case(case):
    v = case.get("victim", {})
    return {"id": case["id"], "title": case["title"], "setting": case["setting"], "briefing": case["briefing"],
            "victim": {"name": v.get("name"), "description": v.get("description"), "cause_of_death_public": v.get("cause_of_death_public")},
            "timeline_public": case.get("timeline_public", [])}

def state(gid):
    g = GAMES[gid]; case, world = g["case"], g["world"]
    return {"game_id": gid, "status": world["game"]["status"], "turn": world["game"]["turn"],
            "clock": world_mod.clock_str(world["game"]["clock_minutes"]), "case": game_case(case),
            "difficulty": world["game"]["difficulty"], "llm_mode": MODE,
            "cast": public_mod.public_cast(case, world), "evidence": world_mod.public_evidence(case, world),
            "locations": public_mod.public_locations(case, world), "turns": g["turns"], "notebook": None,
            "ticker": g["ticker"][-8:], "accessibility": g["accessibility"], "can_rewind_to": []}

def briefing(gid):
    g = GAMES[gid]; case, world = g["case"], g["world"]
    return {"game_id": gid, "title": case["title"], "setting": case["setting"], "briefing": case["briefing"],
            "victim": game_case(case)["victim"], "timeline_public": case.get("timeline_public", []),
            "cast": public_mod.public_cast(case, world), "evidence": world_mod.public_evidence(case, world),
            "locations": public_mod.public_locations(case, world)}

def record(g, outcome):
    g["turns"].extend(outcome.get("public_turns", []))
    g["private"].extend(outcome.get("private_turns", []))
    g["guard"].extend(outcome.get("guard_events", []))
    g["ticker"].extend(outcome.get("tickers", []))
    for ev in outcome.get("world_events", []):
        if isinstance(ev, dict) and ev.get("ticker"): g["ticker"].append(ev["ticker"])

@app.get("/api/health")
def health():
    return {"ok": True, "llm_mode": MODE, "debug_panel": True, "models": {"suspect": os.environ.get("SUSPECT_MODEL", MODE), "author": os.environ.get("AUTHOR_MODEL", MODE), "guard": os.environ.get("GUARD_MODEL", MODE)}, "cases": len(CASES),
            "note": "TEMPORARY in-memory API; the real backend replaces it"}

@app.get("/api/cases")
def cases():
    return [{"id": c["id"], "title": c["title"], "setting": c["setting"], "generated": False, "n_suspects": len(c["suspects"]), "preset": preset(c["setting"])} for c in CASES.values()]

@app.get("/api/games")
def games():
    return [{"game_id": gid, "case_id": g["case"]["id"], "case_title": g["case"]["title"], "setting": g["case"]["setting"], "difficulty": g["world"]["game"]["difficulty"],
             "status": g["world"]["game"]["status"], "turn": g["world"]["game"]["turn"], "created_at": g["created_at"], "correct": (g.get("accusation") or {}).get("correct"), "rank": (g.get("accusation") or {}).get("rank")} for gid, g in GAMES.items()]

@app.post("/api/games", status_code=201)
def create(body: dict):
    case = CASES.get(body.get("case_id"))
    if not case: raise HTTPException(404, {"error": "unknown case"})
    difficulty = body.get("difficulty") or "detective"
    world = world_mod.initial_world(case, difficulty)
    gid = uuid.uuid4().hex[:12]
    d = director_mod.Director(case, world, performer=live.perform, guard=guard, rng=random.Random(gid), difficulty=difficulty,
                              offscreen_every=3, fallback_lines=judge.fallback_lines_scripted(case), fallback_performer=scripted.perform)
    GAMES[gid] = {"case": case, "world": world, "director": d, "turns": [], "private": [], "guard": [], "ticker": [],
                  "accessibility": body.get("accessibility") or {}, "created_at": datetime.datetime.now().isoformat(), "interject": None, "lock": asyncio.Lock()}
    return {"game_id": gid, "briefing": briefing(gid)}

def _g(gid):
    if gid not in GAMES: raise HTTPException(404, {"error": "unknown game"})
    return GAMES[gid]

@app.get("/api/games/{gid}")
def get_game(gid: str): _g(gid); return state(gid)

@app.post("/api/games/{gid}/turn")
async def turn(gid: str, body: dict):
    g = _g(gid)
    async with g["lock"]:
        try: out = await g["director"].player_turn(body)
        except director_mod.DirectorError as e: raise HTTPException(400, {"error": str(e)})
        record(g, out)
        pts = out.get("public_turns", [])
        reply = next((t for t in reversed(pts) if t.get("actor") == body.get("suspect_id")), pts[-1] if pts else None)
        return reply

@app.post("/api/games/{gid}/confront")
async def confront(gid: str, body: dict):
    g = _g(gid)
    async def get_interject():
        t, g["interject"] = g["interject"], None
        return t
    async with g["lock"]:
        try: out = await g["director"].confront(body, get_interject=get_interject)
        except director_mod.DirectorError as e: raise HTTPException(400, {"error": str(e)})
        record(g, out)
        return {"lines": out.get("public_turns", [])}

@app.post("/api/games/{gid}/confront/interject")
def interject(gid: str, body: dict):
    _g(gid)["interject"] = (body.get("text") or "").strip() or None
    return {"ok": True, "queued": bool(_g(gid)["interject"])}

@app.post("/api/games/{gid}/search")
def search(gid: str, body: dict):
    g = _g(gid)
    try: out = g["director"].search(body.get("location_id"))
    except director_mod.DirectorError as e: raise HTTPException(400, {"error": str(e)})
    record(g, out)
    return {"evidence": out.get("evidence") or out.get("examined") or [e for e in world_mod.public_evidence(g["case"], g["world"]) if e["state"] == "examined"], "clock": out.get("clock")}

@app.post("/api/games/{gid}/accuse")
async def accuse(gid: str, body: dict):
    g = _g(gid)
    pts = judge.grade_motive_scripted(body.get("motive_text") or "", g["case"]["solution"]["motive"]).get("points", 0)
    async with g["lock"]:
        try: out = await g["director"].accuse(body, pts)
        except director_mod.DirectorError as e: raise HTTPException(400, {"error": str(e)})
        record(g, out)
        g["accusation"] = out.get("accusation")
        g["debrief"] = debrief_mod.build(g["case"], g["world"], g["private"], g["guard"], g["accusation"], public_mod.public_cast(g["case"], g["world"]), game_id=gid)
        g["debrief"].setdefault("turns", g["turns"])
        return g["debrief"]

@app.get("/api/games/{gid}/debrief")
def get_debrief(gid: str):
    g = _g(gid)
    if not g.get("debrief"): raise HTTPException(404, {"error": "game not closed"})
    return g["debrief"]

@app.post("/api/games/{gid}/retry")
def retry(gid: str):
    g = _g(gid)
    return create({"case_id": g["case"]["id"], "difficulty": g["world"]["game"]["difficulty"], "accessibility": g["accessibility"]})

@app.post("/api/games/{gid}/rewind")
def rewind(gid: str, body: dict):
    raise HTTPException(501, {"error": "rewind arrives with the real backend"})

@app.get("/api/games/{gid}/debug")
def debug(gid: str):
    g = _g(gid); case, world = g["case"], g["world"]
    sus = {}
    for s in case["suspects"]:
        st = world["suspects"][s["id"]]
        sus[s["id"]] = {"name": s["name"], "stress": st["stress"], "thresholds": s["crack_thresholds"], "unlocked": st["unlocked_secret_ids"],
                        "locked": [x["id"] for x in s["secrets"] if x["id"] not in st["unlocked_secret_ids"]], "revealed": st["revealed_secret_ids"],
                        "secrets": [{"id": x["id"], "tier": x["tier"], "text": x["text"], "status": "revealed" if x["id"] in st["revealed_secret_ids"] else ("unlocked" if x["id"] in st["unlocked_secret_ids"] else "locked")} for x in s["secrets"]],
                        "heard_log": st["heard_log"], "outbox": st["outbox"], "emotion": st["emotion"], "last_honesty": st.get("last_honesty"),
                        "last_internal_reasoning": st.get("last_internal_reasoning"), "last_accuses": st.get("last_accuses"), "system_blocks": st.get("last_system_blocks", []), "silenced_until": st.get("silenced_until")}
    return {"llm_mode": MODE, "turn": world["game"]["turn"], "clock": world_mod.clock_str(world["game"]["clock_minutes"]), "suspects": sus,
            "evidence": {k: v["state"] for k, v in world["evidence"].items()}, "guard_events": g["guard"], "world_events": [], "fired_framing_actions": world["game"]["fired_framing_actions"], "cross_contamination": []}

@app.websocket("/api/ws/games/{gid}")
async def ws(websocket: WebSocket, gid: str):
    await websocket.accept()
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: pass
