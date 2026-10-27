# Diagnose → Verify skill → Fix plan

Bespoke playbook for the 2026-10-26 figure-it-out run on Murder Mystery Mayhem / Alibi.

## Definition of done (falsifiable)

1. `GET http://localhost:8000/api/health` returns 200 (or documented failure with evidence).
2. Frontend at `http://localhost:5173` serves the Setup screen (HTTP 200, DOM contains brand text).
3. `docs/BROKEN.md` lists each broken or missing path with measured evidence (command output path, screenshot path, or test name), not guesses.
4. `.cursor/skills/verify-alibi/SKILL.md` exists and `scripts/verify_alibi.sh` exits non-zero when any gate fails, zero when all pass on a healthy scripted boot.
5. `docs/FIX_PLAN.md` sequences work from boot-stable → playable loop → Tapia/DESIGN visual fidelity → isolation proof, with acceptance checks per phase.

Out of scope for this run: implementing the full fix plan, shipping final art, or merging game features.

## Scope

Rough units: 1 boot harness, 1 API smoke, 1 browser smoke, 1 gap inventory, 1 verification skill+script, 1 phased fix plan, 1 PR with decision trail.

Blockers grounded before start: no `backend/.venv`, no `node_modules`, no `.env`; backend may be `scripts/mock_api.py` only (README); Gemini key may be absent (scripted mode still required playable).

## Rigor

High for verification and inventory (those are the product of this run). Medium for visual plan (deck is image-only; DESIGN.md is the executable visual contract; Tapia slide 3 shows illustrative mock targets).

## Units (riskiest unknown first)

| # | Unit | Hypothesis | Check |
|---|------|------------|-------|
| 1 | Setup + boot | `make setup` then backend/frontend bind and answer | curl health + curl 5173 |
| 2 | API play loop | mock_api can create game and run ask/search/present/accuse in scripted mode | curl/httpx script matching PLAYTEST.md |
| 3 | Browser surfaces | each route renders without hard crash | screenshots + console errors |
| 4 | Gap inventory | PLAN/DESIGN/Tapia promised features vs code | BROKEN.md with evidence |
| 5 | Verification skill | encode the checks as a re-runnable skill+script | script green on healthy boot |
| 6 | Fix plan | sequence fixes so each phase ends playable-er | FIX_PLAN.md acceptance lines |

## Audit trail

Committed at `docs/audit/diagnose-verify-plan.tsv`. Local working copy may also live under `.audit/` (gitignored).
