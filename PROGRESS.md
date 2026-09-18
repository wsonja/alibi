# PROGRESS.md

## 2026-09-18 — M0 scaffold
- Repo created from PLAN.md; vane_hall.json copied to backend/app/cases; validate_case.py to scripts/.
- No Anthropic credential on this machine → decided LLM_MODE=auto with a deterministic scripted performer
  (docs/INTERFACES.md §0.1, §5) so the game is playable offline; live Claude suspects activate when a key is added.
- Models pinned: claude-sonnet-5 / claude-opus-5 / claude-haiku-4-5 (INTERFACES §0.2).
- UI branded "Murder Mystery Mayhem" per the owner's mockups (docs/DESIGN.md).
- Frontend scaffolded with Vite 8 + React 19 + Tailwind 4; backend venv with FastAPI 0.141, SQLAlchemy 2.0.54, anthropic 1.7.
