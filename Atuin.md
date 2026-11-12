# Atuin

Let's review the [atuinsh](https://github.com/atuinsh/atuin) tool here.

## Motivation

> Atuin replaces your shell history with a SQLite database, and records extra context for every command: the directory it ran in, how long it took, whether it succeeded, and which machine and session it came from. That context is what makes search actually useful.

This seems quite useful to track user interaction in the terminal.

The [Quickstart](https://docs.atuin.sh/latest/#quickstart) approach involves:
```
curl --proto '=https' --tlsv1.2 -LsSf https://setup.atuin.sh | sh
```

The above approach may be good for end users but I need a better understanding of the various components used.
Once I have a good understanding of `atuinsh` and how it works, we can consider how to integrate it.
Also, I feel that we may not need the complete tool for an appropriate integration.

Hence, to evaluate the tool, we need to use the source code approach for installation.

That is, click on [Manual Installation](https://docs.atuin.sh/latest/guide/installation/#manual-installation) and then choose the Source tab.

## Building from source

`make atuin` runs, from inside `vendor/atuin`:

```
cargo install --path crates/atuin --locked --root $(CURDIR)/.venv
```

* Running inside the submodule lets rustup use the toolchain pinned in Atuin's `rust-toolchain.toml` instead of the default toolchain.
* `--locked` uses the exact dependency versions in `Cargo.lock`.
* `--root` installs into `.venv/bin` instead of `~/.cargo/bin`, so `atuin` is on `PATH` whenever the venv is active.
  * It is absolute (`$(CURDIR)/.venv`) because the recipe first `cd`s into `vendor/atuin` first.
* To list or remove the install: `cargo install --list --root .venv`, `cargo uninstall atuin --root .venv`.

## Trying it out

`make atuin-trial` opens bash with `ATUIN_HOME=.atuin-trial`, so Atuin keeps its config and history there instead of `~/.atuin`, and `~/.bashrc` is left as is. `exit` returns to the normal shell; `rm -rf .atuin-trial` starts over.

`eval "$(atuin init bash)"` exports a per-shell `ATUIN_SESSION`, hooks every command (`atuin history start` before, `atuin history end` after) and binds Ctrl-R / Up to Atuin's search.

Each command becomes a row in the `history` table of `.atuin-trial/data/history.db` (SQLite): `command`, `exit`, `duration` (ns), `cwd`, `session`, `hostname`, `timestamp`. The Collect phase could read this directly.

## Findings

Sync is ignored here, since the goal is local-first. Three things were explored:

1. **`history.db`**: the `history` table stores one row per command: `command`, `exit`, `duration`, `cwd`, `session`, `hostname`, `timestamp`. `timestamp` and `duration` are in nanoseconds.
   * To inspect it: `sqlite3 -readonly .atuin-trial/data/history.db`, then `PRAGMA table_info(history);`.
   * The other tables don't matter for collecting events:
     * `records.db` → `store` holds an encrypted copy of each command for sync.
     * `records.db` → `records` is an old, unused table.
     * `meta.db` → `meta` holds key/value settings such as `host_id`.
2. **Search UI** (Up / Ctrl-R): an interactive view of the same table, showing duration, time and command, filterable by directory, session and so on.
3. **`atuin stats`**: the most-used commands and total/unique counts, also computed from the `history` table.

None of these capture what a command printed. They only record that it ran, and its exit code and duration.

## Outlook: command output

Atuin v18.24.5 has an opt-in output capture feature (`vendor/atuin/docs/docs/guide/output-capture.md`). It is off in the current trial config:

* To enable it: `atuin config enable output-capture` (this turns on `[daemon]`, `[pty_proxy]` and `[output]`), then open a new shell.
* `atuin pty-proxy` runs the shell inside a virtual terminal. The daemon stores each command's output, linked to its history entry, under `<data_dir>/output-capture/`. This is a separate store, not part of `history.db`.
* To read it: press Ctrl-O in search, `atuin output search <text>`, or use Atuin's MCP server.
* Limits:
  * Only the final screen is stored; for example, a progress bar is saved as its last frame.
  * Full-screen programs like `vim` and `less` are skipped.
  * Output over 1 MB keeps only its start and end.
  * Recognised secrets are replaced with `****`.
* Captured output stays local and is never synced.

Next step: enable it in `.atuin-trial`, then check whether the stored output can be read outside Atuin, for example with `atuin output search` or MCP, for the Collect phase.
