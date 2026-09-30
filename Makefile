.PHONY: all install check lint typecheck test format clean run core-up core-down lab-up lab-down lab-reset lab-attack

all: check

install:
	uv sync --all-extras

lint:
	uv run ruff check src tests

typecheck:
	uv run mypy src tests

test:
	uv run pytest

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

check: lint typecheck test

run:
	uv run python -m sentinelx_controller.main

# Docker Compose targets
core-up:
	docker compose --profile core up -d --build

core-down:
	docker compose --profile core down

lab-up:
	docker compose --profile lab up -d --build

lab-down:
	docker compose --profile lab down

lab-attack:
	docker compose --profile attack up -d --build

lab-reset:
	bash scripts/lab_reset.sh

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').glob('.*cache')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').glob('*.egg-info')]"
