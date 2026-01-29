
# Use the default_python_version set in .zshrc
# Edit if it needs to be over-written for the project
PYTHON_VERSION=${default_python_version}

default: test lint

help:
	@echo
	@echo "Makefile commands are:"
	@echo "  default      - runs make lint"
	@echo "  install      - install a new runtime virtual env"
	@echo "  install-gui  - install GUI dependencies (PyQt6, PyInstaller)"
	@echo "  lint         - run prospector linter"
	@echo "  run-gui      - run the GUI application"
	@echo "  build-mac    - build macOS .app bundle"
	@echo "  build-win    - build Windows .exe (run on Windows)"
	@echo "  clean-build  - remove build artifacts"
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

install-gui:
	@echo "--> Installing GUI dependencies"
	./venv/bin/pip install PyQt6>=6.4.0 pyinstaller>=6.0.0

lint:
	prospector

run-gui:
	@echo "--> Running Aura Frame Downloader GUI"
	./venv/bin/python aura_gui.py

build-mac:
	@echo "--> Building macOS application bundle"
	./venv/bin/pyinstaller aura_gui.spec
	@echo "--> Build complete: dist/Aura Downloader.app"

build-win:
	@echo "--> Building Windows executable"
	./venv/Scripts/pyinstaller.exe aura_gui.spec
	@echo "--> Build complete: dist/Aura Downloader.exe"

clean-build:
	@echo "--> Removing build artifacts"
	rm -rf build dist *.spec.bak
