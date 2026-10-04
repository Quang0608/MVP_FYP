.PHONY: backend frontend test
backend:
	uvicorn backend.app.main:app --reload
frontend:
	cd frontend && npm install && npm run dev
test:
	pytest backend/tests
