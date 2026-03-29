PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

.PHONY: install run run-fast verify reproduce clean update-lock

install: $(VENV_PYTHON)

$(VENV_PYTHON): requirements-lock.txt
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements-lock.txt

run: install
	$(VENV_PYTHON) run.py

run-fast: install
	$(VENV_PYTHON) run.py --no-mc

verify: install
	$(VENV_PYTHON) run.py --csv --verify-manifest
	$(VENV_PYTHON) -m tests.test_determinism
	$(VENV_PYTHON) -m tests.test_artifact_manifest

reproduce: verify

clean:
	rm -rf data figures

update-lock: install
	$(VENV_PIP) freeze > requirements-lock.txt
