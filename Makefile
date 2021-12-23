all : black mypy isort flake8

.PHONY: black
black:
	black heim tests

.PHONY: mypy
mypy:
	mypy heim tests

.PHONY: isort
isort:
	isort heim tests

.PHONY: flake8
flake8:
	flake8 heim tests
