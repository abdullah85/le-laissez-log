# Build ActivityWatch from source (vendor/activitywatch submodule) into a
# project-local venv, then install this project's own dependencies.
#
#   make setup    # once: submodules + venv + ActivityWatch build + deps
#   make atuin    # optional: build Atuin from vendor/atuin into the venv
#   make atuin-trial  # optional: try Atuin in a shell, history kept in .atuin-trial/
#   make server   # start aw-server in testing mode (port 5666)
#   make run      # start the terminal watcher against the testing server

PYTHON ?= python3.12
VENV   := .venv
BIN    := $(VENV)/bin
AW     := vendor/activitywatch
ATUIN  := vendor/atuin

.PHONY: setup submodules venv aw atuin atuin-trial deps server run clean

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

# Run from inside the submodule so rustup picks up its pinned rust-toolchain.toml.
atuin: venv
	cd $(ATUIN) && cargo install --path crates/atuin --locked --root $(CURDIR)/$(VENV)

# ATUIN_HOME keeps Atuin's config and history out of ~/.atuin.
atuin-trial:
	ATUIN_HOME=$(CURDIR)/.atuin-trial ATUIN_UPDATE_CHECK=false bash --rcfile scripts/atuin-trial.bashrc -i

deps: venv
	$(BIN)/pip install -r requirements.txt

server:
	$(BIN)/aw-server --testing

run:
	$(BIN)/python aw_watcher_terminal.py --testing

clean:
	rm -rf $(VENV)
