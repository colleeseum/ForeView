# SPDX-FileCopyrightText: 2026 Mindstep Corporation
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

.PHONY: install-dev diff-check identity-check license-check format format-check lint javascript javascript-coverage javascript-audit typecheck test coverage integration-coverage coverage-target coverage-gate security audit qa load-questrade-dev load-expenses-dev update-public-rules

PYTHON := .venv/bin/python

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt
	npm ci

diff-check:
	git --no-pager diff --check HEAD

identity-check:
	./scripts/check-git-identity.sh

license-check:
	./scripts/check-license-headers.sh

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

format-check:
	$(PYTHON) -m ruff format --check .

lint:
	$(PYTHON) -m ruff check .

javascript:
	@for file in static/*.mjs; do node --check $$file || exit 1; done
	npm test

javascript-coverage:
	npm run coverage

javascript-audit:
	npm run audit

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest -q

coverage:
	$(PYTHON) -m pytest --cov=. --cov-branch --cov-report=term-missing --cov-report=xml
	$(PYTHON) -m coverage report --include='repositories/*.py,services/*.py' --fail-under=80
	$(PYTHON) -m coverage report --include=app.py --fail-under=80

integration-coverage:
	COVERAGE_FILE=.coverage.integration $(PYTHON) -m pytest tests/test_app_routes.py tests/test_runtime_profiles.py tests/test_synthetic_documents.py tests/test_import_idempotency.py tests/test_expense_import_routes.py tests/test_expense_import_service.py tests/test_reconciliation_checkpoints.py tests/test_transaction_balance_recalculation.py tests/test_tax_notice_parsers.py tests/test_ufile_tax_return_parser.py tests/test_retraite_quebec_statement_parser.py --cov=. --cov-branch --cov-fail-under=0 --cov-report=term-missing --cov-report=xml:coverage-integration.xml
	COVERAGE_FILE=.coverage.integration $(PYTHON) -m coverage report --include='repositories/*.py,services/*.py' --omit='services/runtime_backup_service.py' --fail-under=80

coverage-target:
	$(PYTHON) -m pytest --cov=. --cov-branch --cov-report=term-missing --cov-fail-under=80

coverage-gate:
	npm run coverage
	$(PYTHON) -m pytest --cov=. --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=80

security:
	$(PYTHON) -m bandit -c pyproject.toml -r app.py runtime_backup.py synthetic_documents.py synthetic_expenses.py synthetic_questrade.py synthetic_runtime.py domain infrastructure ingestion institution_support institutions projection repositories services web

audit:
	$(PYTHON) -m pip_audit -r requirements.txt

load-questrade-dev:
	$(PYTHON) synthetic_questrade.py .runtime/dev --scenario initial

load-expenses-dev:
	$(PYTHON) synthetic_expenses.py .runtime/dev

update-public-rules:
	$(PYTHON) update_public_rules.py

qa: diff-check identity-check license-check format-check lint javascript javascript-coverage javascript-audit typecheck coverage integration-coverage security audit
