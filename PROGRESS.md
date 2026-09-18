# PROGRESS.md

## 2026-09-18 — M0 scaffold
- Repo created from PLAN.md; vane_hall.json copied to backend/app/cases; validate_case.py to scripts/.
- No Anthropic credential on this machine → decided LLM_MODE=auto with a deterministic scripted performer
  (docs/INTERFACES.md §0.1, §5) so the game is playable offline; live Claude suspects activate when a key is added.
- Models pinned: claude-sonnet-5 / claude-opus-5 / claude-haiku-4-5 (INTERFACES §0.2).
- UI branded "Murder Mystery Mayhem" per the owner's mockups (docs/DESIGN.md).
- Frontend scaffolded with Vite 8 + React 19 + Tailwind 4; backend venv with FastAPI 0.141, SQLAlchemy 2.0.54, anthropic 1.7.

## 2026-09-18 — provider switch
- Owner supplied a Gemini API key; provider is Google Gemini via google-genai 2.24 (INTERFACES §0.1–0.2). Anthropic
  SDK removed from the plan. Verified on the key: gemini-3.5-flash-lite / 3.1-flash-lite answer structured JSON in
  ~2 s; bigger flash models 503 under load; pro + image models 429 (quota). Model ladder + scripted fallback per turn.

## 2026-09-18 — provider switch to Gemini
- Owner supplied a Gemini API key and asked not to use Anthropic. Provider switched (docs/INTERFACES.md §0.1–0.4).
- Probe results on this key: gemini-2.5-* retired (404); pro + image models quota-blocked (429); 3.8/3.7/3.5-flash 503
  on every attempt; 3.6-flash works but slow (~25 s); 3.5-flash-lite / 3.1-flash-lite ~2 s with valid JSON.
  → model ladders in backend/.env.example; suspects default to gemini-3.5-flash-lite.
- Structured JSON output (response_json_schema) replaces forced tool use. Scripted performer remains the offline/fallback path.
