all : black mypy isort flake8

.PHONY: black
black:
	black --check heim tests

.PHONY: mypy
mypy:
	mypy heim tests

.PHONY: isort
isort:
	isort --check-only heim tests

.PHONY: flake8
flake8:
	flake8 heim tests
