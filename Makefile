.PHONY: backend dashboard test
backend:
	uvicorn backend.app.main:app --reload
dashboard:
	streamlit run dashboard/streamlit_app.py
test:
	pytest backend/tests
