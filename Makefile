all : black mypy isort flake8

.PHONY: black
black:
	black weather_station tests

.PHONY: mypy
mypy:
	mypy weather_station tests

.PHONY: isort
isort:
	isort weather_station tests

.PHONY: flake8
flake8:
	flake8 weather_station tests
