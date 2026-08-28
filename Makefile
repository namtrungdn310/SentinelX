.PHONY: all install check lint typecheck test format clean

all: check

install:
	python -m pip install -e ".[dev]"

lint:
	python -m ruff check src tests

typecheck:
	python -m mypy src

test:
	python -m pytest

format:
	python -m ruff format src tests
	python -m ruff check --fix src tests

check: lint typecheck test

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').glob('.*cache')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').glob('*.egg-info')]"
