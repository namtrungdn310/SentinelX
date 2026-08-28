.PHONY: all install check lint typecheck test format clean run

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

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').glob('.*cache')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').glob('*.egg-info')]"
