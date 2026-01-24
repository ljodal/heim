all: lint mypy

.PHONY: lint
lint:
	ruff check heim tests
	ruff format --check heim tests

.PHONY: mypy
mypy:
	mypy heim tests

.PHONY: fix
fix:
	ruff check --fix heim tests
	ruff format heim tests
