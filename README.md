# Murder Mystery Mayhem (codename Alibi)

A browser murder-mystery where every suspect is its own LLM agent with private knowledge and secrets. You question
suspects, search rooms, present evidence, use tactics (bluff / flatter / threaten / silence), put two suspects in a
room together, then accuse. Suspects run on Google Gemini when a key is present, or on a built-in scripted performer
when it isn't, so the game is playable offline too.

**Status: demo MVP.** Setup, Briefing, Investigation and Case Closed screens over a temporary in-memory API
(`scripts/mock_api.py`) that runs the real game engine. The persistent FastAPI backend (`backend/app/main.py`), Judge
panel, sensors and campaign archive are in progress (see `PLAN.md`, `docs/INTERFACES.md`, `PROGRESS.md`).

## Run it

Requirements: Python 3.11+, Node 20+.

```bash
git clone https://github.com/wsonja/alibi.git && cd alibi
make setup            # creates backend/.venv, installs Python + npm deps, copies backend/.env.example to backend/.env
```

Optional but recommended: put a Gemini key in `backend/.env` (`GEMINI_API_KEY=...`, free at aistudio.google.com).
Without it the suspects are scripted (still playable, less witty).

Then, in two terminals:

```bash
make backend          # API on http://localhost:8000
```

```bash
make frontend         # game on http://localhost:5173
```

Open http://localhost:5173, pick a case, press Begin.

## Cases

Four hand-written cases live in `backend/app/cases/`: Death at Vane Hall (manor, 1923), Death on the RMS Caledonia
(ocean liner, 1927), The Pitch That Kills (startup office), Secrets on Campus (a Cornell overflow dorm). Validate a
case with `backend/.venv/bin/python scripts/validate_case.py backend/app/cases/<file>.json`.

## How to play (Vane Hall spoiler-free hints)

Ask everyone where they were. Search rooms: evidence found there can be presented to a suspect and raises their
pressure. Flattery works on some people, threats on others. Secrets unlock as pressure crosses each suspect's
thresholds, and some only unlock once you hold specific evidence. Accuse when you have the who, the how and the why.

## Development

```bash
make test             # backend unit tests (scripted mode, no network)
cd frontend && npx tsc --noEmit -p tsconfig.app.json && npm run build
```

Layout: `backend/app/engine` (deterministic director: stress, unlocks, confrontations, rumors, world, scoring,
debrief), `backend/app/agents` (Gemini client, suspect prompts, scripted performer, leak guard, Watson notebook,
case author/checker), `frontend/src` (React 19 + Vite + Tailwind; screens, store, pixel-art portraits).
