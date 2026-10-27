.PHONY: install lint typecheck test e2e up down clean

PY ?= python3

install:
	$(PY) -m pip install -e ".[dev]"

lint:
	$(PY) -m ruff check src tests

typecheck:
	$(PY) -m mypy src --follow-imports=skip

test:
	$(PY) -m pytest -q

e2e:
	$(PY) scripts/generate_synthetic_traces.py
	$(PY) scripts/run_e2e.py --config configs/development.yaml

up:
	docker compose up -d --build

down:
	docker compose down

clean:
	rm -rf reports .agentevalops datasets/synthetic/agent_behavior_v1__* .pytest_cache .mypy_cache .ruff_cache
