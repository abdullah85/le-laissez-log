# Build ActivityWatch from source (vendor/activitywatch submodule) into a
# project-local venv, then install this project's own dependencies.
#
#   make setup    # once: submodules + venv + ActivityWatch build + deps
#   make server   # start aw-server in testing mode (port 5666)
#   make run      # start the terminal watcher against the testing server

PYTHON ?= python3.12
VENV   := .venv
BIN    := $(VENV)/bin
AW     := vendor/activitywatch

.PHONY: setup submodules venv aw deps server run clean

setup: submodules aw deps

submodules:
	git submodule update --init --recursive

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

venv: $(BIN)/python

# Python aw-server only; drop SKIP_SERVER_RUST to also build aw-server-rust and awatcher.
aw: venv
	. $(BIN)/activate && $(MAKE) -C $(AW) build SKIP_SERVER_RUST=true

deps: venv
	$(BIN)/pip install -r requirements.txt

server:
	$(BIN)/aw-server --testing

run:
	$(BIN)/python aw_watcher_terminal.py --testing

clean:
	rm -rf $(VENV)
