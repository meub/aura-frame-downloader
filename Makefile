
# Use the default_python_version set in .zshrc
# Edit if it needs to be over-written for the project
PYTHON_VERSION=${default_python_version}

default: test lint

help:
	@echo
	@echo "Makefile commands are:"
	@echo "  default      - runs make lint"
	@echo "  install      - install a new runtime virtual env"
	@echo "  lint         - run prospector linter"
	@echo

install: clean-venv install-venv install-packages

clean-venv:
	@if [ -d ./venv ];  then \
 		echo "--> Removing old ./venv"; \
 		rm -r ./venv; \
 	fi

install-venv:
	@echo "--> Installing new ./venv"
	${HOME}/.pyenv/versions/${PYTHON_VERSION}/bin/python -m venv venv

install-packages:
	@echo "--> Installing runtime packages into the venv"
	./venv/bin/pip install --upgrade pip setuptools wheel
	./venv/bin/pip install -r ./requirements.txt

lint:
	prospector

