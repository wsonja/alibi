PY=backend/.venv/bin/python
.PHONY: dev backend frontend test test-integration redteam smoke types reset-db ping-models lint
dev:
	@echo "Starting backend :8000 and frontend :5173"; \
	(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev -- --port 5173); wait
backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
frontend:
	cd frontend && npm run dev -- --port 5173
test:
	cd backend && .venv/bin/python -m pytest -q -m "not integration"
test-integration:
	cd backend && .venv/bin/python -m pytest -q -m integration
redteam:
	cd backend && .venv/bin/python ../scripts/redteam.py
smoke:
	@cat scripts/smoke.md
types:
	cd frontend && npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.gen.ts
reset-db:
	rm -f backend/alibi.db
ping-models:
	cd backend && .venv/bin/python ../scripts/ping_models.py
lint:
	cd backend && .venv/bin/ruff check app tests; cd frontend && npx oxlint src
