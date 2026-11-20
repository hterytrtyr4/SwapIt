# SwapIt — developer shortcuts
#
#   make            # show this help
#   make install    # create .venv and install requirements
#   make run        # start the dev server on http://127.0.0.1:5000
#   make dev        # install (if needed) + seed demo data + run
#   make test       # run the 35-test suite
#   make seed       # load demo users / listings
#   make reset      # wipe the local database and uploads, then reseed
#   make clean      # remove caches and test artifacts
#
# Everything runs through the project-local virtualenv when it exists,
# otherwise through the system Python. No extra tooling required.

PYTHON ?= python3
VENV   ?= .venv
BIN     = $(VENV)/bin
UNAME  := $(shell uname -s)

ifeq ($(OS),Windows_NT)
  BIN = $(VENV)/Scripts
endif

# Use the venv interpreter when it has been created, else the system one.
ifeq ($(wildcard $(BIN)/python*),)
  PY = $(PYTHON)
else
  PY = $(BIN)/python
endif

PORT ?= 5000
HOST ?= 0.0.0.0

.DEFAULT_GOAL := help
.PHONY: help install run dev test seed reset clean check health

help:
	@echo "SwapIt — available targets"
	@echo ""
	@echo "  make install   Create $(VENV)/ and install requirements.txt"
	@echo "  make run       Start the dev server (HOST=$(HOST) PORT=$(PORT))"
	@echo "  make dev       install + seed + run  (first-time friendly)"
	@echo "  make test      Run the automated test-suite"
	@echo "  make seed      Load demo users, listings and swaps"
	@echo "  make reset     Delete the local SQLite DB + uploads, then reseed"
	@echo "  make check     Compile-check the sources and print versions"
	@echo "  make health    Curl the running server (requires it to be up)"
	@echo "  make clean     Remove __pycache__, test uploads and caches"
	@echo ""

install:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(BIN)/python -m pip install --quiet --upgrade pip
	@$(BIN)/python -m pip install --quiet -r requirements.txt
	@echo "Dependencies installed in $(VENV)/"

run:
	@echo "Starting SwapIt on http://127.0.0.1:$(PORT)  (Ctrl+C to stop)"
	@HOST=$(HOST) PORT=$(PORT) $(PY) app.py

dev: install seed
	@$(MAKE) --no-print-directory run

test:
	@$(PY) -m unittest discover -s tests -v

seed:
	@$(PY) seed_demo.py

reset:
	@rm -rf instance static/uploads/*.jpg static/uploads/*.png static/uploads/*.jpeg
	@mkdir -p static/uploads && touch static/uploads/.gitkeep
	@echo "Local database and uploads cleared."
	@$(MAKE) --no-print-directory seed

check:
	@$(PY) -m py_compile app.py config.py models.py matching.py seed_demo.py \
		routes/*.py api/index.py tests/test_app.py
	@echo "Sources compile cleanly."
	@$(PY) -c "import sys, flask, sqlalchemy; print('python', sys.version.split()[0]); \
print('flask', flask.__version__ if hasattr(flask, '__version__') else 'ok'); \
print('sqlalchemy', sqlalchemy.__version__)"

health:
	@curl -fsS -o /dev/null -w "GET /            %{http_code}\n" http://127.0.0.1:$(PORT)/ \
	  && curl -fsS -o /dev/null -w "GET /marketplace %{http_code}\n"  http://127.0.0.1:$(PORT)/marketplace \
	  && echo "Server is healthy."

clean:
	@find . -type d -name __pycache__ -not -path "./$(VENV)/*" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf tests/_uploads .pytest_cache .mypy_cache .coverage htmlcov
	@echo "Caches and test artifacts removed."
