# Atuin

Let's review the [atuinsh](https://github.com/atuinsh/atuin) here first.

## Motivation

> Atuin replaces your shell history with a SQLite database, and records extra context for every command: the directory it ran in, how long it took, whether it succeeded, and which machine and session it came from. That context is what makes search actually useful.

This seems quite useful to track user interaction in the terminal.

The [Quickstart](https://docs.atuin.sh/latest/#quickstart) approach involves:
```
curl --proto '=https' --tlsv1.2 -LsSf https://setup.atuin.sh | sh
```

The above approach may be good for end users but not suitable for integration.

Hence, to evaluate the tool, we need to use the source code approach for installation.

That is, click on [Manual Installation](https://docs.atuin.sh/latest/guide/installation/#manual-installation) and then choose the Source tab.

## Building from source

`make atuin` runs, from inside `vendor/atuin`:

```
cargo install --path crates/atuin --locked --root $(CURDIR)/.venv
```

* Running from inside the submodule lets rustup apply Atuin's `rust-toolchain.toml` (1.98.0); the system default is older than the workspace's `rust-version` (1.95.0).
* `--locked` builds the exact dependency versions in `Cargo.lock`.
* `--root` is the directory cargo puts `bin/` under (default `~/.cargo`, which is not on our `PATH`). Pointing it at the venv puts `atuin` next to the other project tools, so it is on `PATH` whenever the venv is active. It is absolute (`$(CURDIR)/...`) because the recipe `cd`s first.
* Cargo records the install in `.venv/.crates.toml` and `.venv/.crates2.json`, so `cargo install --list --root .venv` and `cargo uninstall atuin --root .venv` work.

## Trying it out

`make atuin-trial` opens bash with `ATUIN_HOME=.atuin-trial`, so Atuin keeps its config and history there instead of `~/.atuin`, and `~/.bashrc` is left as is. `exit` returns to the normal shell; `rm -rf .atuin-trial` starts over.

`eval "$(atuin init bash)"` exports a per-shell `ATUIN_SESSION`, hooks every command (`atuin history start` before, `atuin history end` after) and binds Ctrl-R / Up to Atuin's search.

Each command becomes a row in the `history` table of `.atuin-trial/data/history.db` (SQLite): `command`, `exit`, `duration` (ns), `cwd`, `session`, `hostname`, `timestamp`. The Collect phase could read this directly.
