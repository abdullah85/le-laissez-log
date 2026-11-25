# Debugging Atuin's bash hooks

How to step through the bash side of Atuin, one command at a time, in VS Code. See [Atuin.md](Atuin.md) for the rest of the flow (pty-proxy and the daemon).

## What runs

`eval "$(atuin init bash)"` loads `atuin.bash` ([upstream](https://github.com/atuinsh/atuin/blob/ad5bf5c35b7788c05b8d936f5da59c9ab1ac320e/crates/atuin/src/shell/atuin.bash) · [local](../vendor/atuin/crates/atuin/src/shell/atuin.bash)). Around every command, bash calls two of its functions:

```text
__atuin_preexec "echo …"            before the command
   94  id=$(atuin history start …)  new history ID (row kept by the daemon until the end)
   95  export ATUIN_HISTORY_ID=$id
   96  __atuin_mark_output_start → 42: printf OSC 18188735;C;<id>

eval "echo …"                        the command itself

__atuin_precmd                       after the command
  101  EXIT=$?                       the command's exit code
  146  __atuin_mark_output_end → 53: printf OSC 18188735;D;<id>
  147  (atuin history end --exit … &)  finish the history row, in the background
  148  ATUIN_HISTORY_ID=""
```

Line links: [94](https://github.com/atuinsh/atuin/blob/ad5bf5c35b7788c05b8d936f5da59c9ab1ac320e/crates/atuin/src/shell/atuin.bash#L94) · [local](../vendor/atuin/crates/atuin/src/shell/atuin.bash#L94), [42](https://github.com/atuinsh/atuin/blob/ad5bf5c35b7788c05b8d936f5da59c9ab1ac320e/crates/atuin/src/shell/atuin.bash#L42) · [local](../vendor/atuin/crates/atuin/src/shell/atuin.bash#L42), [101](https://github.com/atuinsh/atuin/blob/ad5bf5c35b7788c05b8d936f5da59c9ab1ac320e/crates/atuin/src/shell/atuin.bash#L101) · [local](../vendor/atuin/crates/atuin/src/shell/atuin.bash#L101), [53](https://github.com/atuinsh/atuin/blob/ad5bf5c35b7788c05b8d936f5da59c9ab1ac320e/crates/atuin/src/shell/atuin.bash#L53) · [local](../vendor/atuin/crates/atuin/src/shell/atuin.bash#L53), [147](https://github.com/atuinsh/atuin/blob/ad5bf5c35b7788c05b8d936f5da59c9ab1ac320e/crates/atuin/src/shell/atuin.bash#L147) · [local](../vendor/atuin/crates/atuin/src/shell/atuin.bash#L147).

The markers are printed only when pty-proxy owns the terminal (`__atuin_pty_proxy_owns_tty=1`, `ATUIN_PTY_PROXY_ACTIVE=2`). pty-proxy uses them to cut out the command's output.

## Stepping through it

[scripts/debug-atuin-hooks.sh](../scripts/debug-atuin-hooks.sh) loads `atuin.bash`, pretends pty-proxy owns the terminal, and calls the two hooks by hand around one command (default `echo debug-hooks-test`, or the first argument).

Needs the Bash Debug extension (`rogalmic.bash-debug`).

1. Open `vendor/atuin/crates/atuin/src/shell/atuin.bash` and set breakpoints on lines 94, 96, 101 and 147.
2. Run and Debug (Ctrl-Shift-D) → **"atuin bash hooks (.atuin-output)"** → F5. It stops at the top of the script; F5 again runs to line 94.
3. F10 steps over, F11 steps into (e.g. line 96 into `__atuin_mark_output_start`), F5 runs to the next breakpoint. Hover, or add a Watch for `id`, `ATUIN_HISTORY_ID`, `EXIT` and `cmd` (bare names; `$1` shows the debugger's own arguments, and `cmd` holds the same value).

What to look for:

* After line 94, `id` holds a new ID such as `01a1…`, the same `id` used in `history.db` and the output store.
* The markers print nothing visible; they are escape codes the terminal swallows.
* Line 147 runs in the background (`&`), so stepping over it returns at once.
* If breakpoints in `atuin.bash` stay grey (unverified), press F11 on the `__atuin_preexec` line of the script to step into it.
* F11 on lines 94 and 147 does not enter Atuin: they start a separate `atuin` process (the release build from `.venv/bin`), which bashdb cannot follow. See the next section.

## Stepping into `atuin history start` and `end`

Two lldb launch configs run what lines 94 and 147 run, using the debug build (`cd vendor/atuin && cargo build -p atuin`). Needs the CodeLLDB extension.

* **"atuin history start (debug build, .atuin-output)"** asks for the command line and prints the new history ID.
* **"atuin history end (debug build, .atuin-output)"** asks for that ID and finishes the row with exit 0.

The questions come from the `inputs` section at the bottom of [launch.json](../.vscode/launch.json). An argument such as `${input:atuinCommand}` names an input there; a `promptString` input opens a text box on F5, with its `description` as the prompt and its `default` filled in. The answer replaces the `${input:…}` argument.

| Input | Used by | Default |
|---|---|---|
| `atuinCommand` | history start | `echo debug-hooks-test`, the same as `debug-atuin-hooks.sh`, so rows from both look alike |
| `atuinHistoryId` | history end | none: paste the ID `history start` printed |
| `atuinQuery` | output search | `capture` |

Set breakpoints before launching, or the run finishes without stopping. In [history.rs](../vendor/atuin/crates/atuin/src/command/client/history.rs):

* `start_history_entry` ([535](../vendor/atuin/crates/atuin/src/command/client/history.rs#L535)): F11 into `make_starting_history`, which builds the `History` row.
* `end_history_entry` ([568](../vendor/atuin/crates/atuin/src/command/client/history.rs#L568)).
* `handle_start` ([426](../vendor/atuin/crates/atuin/src/command/client/history.rs#L426)) and `handle_end` ([442](../vendor/atuin/crates/atuin/src/command/client/history.rs#L442)): save to SQLite directly.

Both go to the daemon first and fall back to SQLite when it can't be reached. These configs don't autostart the daemon, so:

1. **Without a daemon**: the daemon call fails, and `handle_start` / `handle_end` run in the same process.
2. **With the daemon**: start "atuin daemon (debug build, .atuin-output)" first, and set breakpoints in its `start_history` and `end_history` ([grpc/history/mod.rs:58](../vendor/atuin/crates/atuin-daemon/src/grpc/history/mod.rs#L58), [72](../vendor/atuin/crates/atuin-daemon/src/grpc/history/mod.rs#L72)). The client now returns early, and the row is saved in the daemon process. Running "atuin bash hooks" also hits these, straight from the bash script.

Until `history end` runs, the row has `duration` and `exit` set to -1.

## Seeing the markers

Run the script without the debugger and make the escape codes visible:

```bash
ATUIN_HOME=$PWD/.atuin-output ATUIN_DAEMON__ENABLED=true ATUIN_DAEMON__AUTOSTART=true ATUIN_OUTPUT__ENABLED=true \
  bash scripts/debug-atuin-hooks.sh | cat -v
```

```text
^[]18188735;C;01a1ed8290c472ef9ab3445fa63b0540^Gdebug-hooks-test
^[]18188735;D;01a1ed8290c472ef9ab3445fa63b0540^G
```

`^[` is ESC and `^G` is BEL. Warnings from `stty` and `bind` are expected, since the script is not an interactive shell.

## Notes

* The bash tricks used in the hooks (`EPOCHREALTIME`, `${var-}`, `declare -p` and others) are explained in [Bash-learnings.md](Bash-learnings.md).

* Each run adds one row to `.atuin-output/data/history.db` (e.g. `echo debug-hooks-test`, exit 0), but no output: nothing reads the markers without pty-proxy.
* The run autostarts a daemon on `.atuin-output`, which keeps running. To stop it: `ATUIN_HOME=$PWD/.atuin-output .venv/bin/atuin daemon stop`. Wait a second first, so the background `atuin history end` can finish.
