all: lint typecheck

.PHONY: lint
lint:
	ruff check heim tests
	ruff format --check heim tests

.PHONY: typecheck
typecheck:
	mypy
	ty check heim

.PHONY: fix
fix:
	ruff check --fix heim tests
	ruff format heim tests
