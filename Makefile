.PHONY: help install dev test lint defs bench-startup clean

help:
	@echo "install       Install runtime + dev dependencies"
	@echo "dev           Run the app (no --reload; see README for dev mode)"
	@echo "test          Run the test suite"
	@echo "lint          Run ruff"
	@echo "defs          Rebuild data/hl7defs.sqlite3 from hl7-dictionary"
	@echo "bench-startup Show what import actually costs"
	@echo "clean         Remove caches and build inputs"

install:
	pip install -r requirements-dev.txt

dev:
	uvicorn main:app

test:
	pytest -q

lint:
	ruff check .

defs:
	python tools/build_defs_db.py

bench-startup:
	@python -X importtime -c "import main" 2>&1 | sort -t'|' -k2 -rn | head -12
	@python -c "import main, sys; \
	  assert not [m for m in sys.modules if m.startswith('hl7apy.v2_')], 'version libs loaded at import'; \
	  from app.defs import store; \
	  assert not hasattr(store._local, 'connection'), 'definition store opened at import'; \
	  print('OK: no definition or version data loaded at import')"

clean:
	rm -rf .pytest_cache .ruff_cache data/vendor
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
