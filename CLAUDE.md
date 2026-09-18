# Alibi / Murder Mystery Mayhem
Multi-agent murder-mystery game. Read PLAN.md, docs/INTERFACES.md and docs/DESIGN.md before doing anything; PLAN.md §2 is non-negotiable.

## Commands
make dev · make backend · make frontend · make test · make redteam · make types · make reset-db · make ping-models · make lint

## Rules
- One Claude call per suspect per turn. A suspect's context never contains another suspect's
  secrets, another suspect's knowledge, or the case solution. The scripted performer obeys the same rule.
- engine/ is deterministic and never imports anthropic or app.agents. agents/ is the only package that imports anthropic.
- Every Claude call uses forced tool use; validate every field; log invalid output.
- No secret, internal_reasoning, honesty, reveals, wants_to_tell, points_to, heard_log or solution
  field may appear in any API response except /debug (and the Debrief once the game is closed).
- Write the turn and its snapshot to the DB before returning a response.
- Log decisions in PROGRESS.md. Keep docs/INTERFACES.md in sync when a contract changes.
- Backend runs from backend/.venv (Python 3.12). Frontend: `cd frontend && npm run dev` (port 5173). Backend: port 8000.
