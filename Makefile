.PHONY: install test run compose

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

test:
	.venv/bin/pytest -q

run:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

compose:
	docker compose up --build
