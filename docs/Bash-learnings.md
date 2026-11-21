# Bash learnings

Things learnt while stepping through Atuin's bash hooks ([Atuin-bash-hooks.md](Atuin-bash-hooks.md)). Line numbers refer to `vendor/atuin/crates/atuin/src/shell/atuin.bash`.

## `EPOCHREALTIME`: the current time, to the microsecond

A special variable in bash 5.0 and later. Every time it is read, bash fills in the current time in seconds since 1 January 1970, always with 6 digits after the decimal point:

```console
$ echo $EPOCHREALTIME
1795052928.385940
$ echo $EPOCHREALTIME
1795052929.893049
```

Atuin reads it before a command (line 97) and after it (line 101) to measure how long the command ran.

## `${var-}`: empty if unset

`${var-}` is the value of `var`, or an empty string if `var` is not set. It changes nothing when the variable exists, but protects against two cases:

* bash older than 5.0, which has no `EPOCHREALTIME`;
* shells running with `set -u`, where reading an unset variable is an error:

```console
$ set -u
$ echo "[${X-}]"
[]
$ echo "[$X]"
bash: X: unbound variable
```

## `${var//[!0-9]}`: arithmetic without decimals

Bash arithmetic only works with whole numbers. Atuin deletes every non-digit, which turns seconds into microseconds:

```console
$ t=1795052928.385940
$ echo ${t//[!0-9]}
1795052928385940
```

`${var//pattern}` removes every match of `pattern`; `[!0-9]` matches any character that is not a digit. It removes any non-digit rather than just `.`, because some locales use a comma as the decimal separator.

The duration is then the difference of the two, in microseconds; appending `000` gives nanoseconds, the unit `history.db` uses (lines 135–137):

```text
1795052929893049 - 1795052928385940 = 1507109 µs  →  1507109000 ns (≈ 1.5 s)
```

## `${var:+word}`: an option only when there is a value

`${var:+word}` gives `word` if `var` is set and not empty, and nothing otherwise. Atuin uses it to pass `--duration` only when one was measured (line 147):

```console
$ d=""; set -- ${d:+"--duration=$d"}; echo $#
0
$ d=5;  set -- ${d:+"--duration=$d"}; echo $#
1
```

## `$( … )` and `2>/dev/null`: keep the output, drop the errors

```bash
id=$(ATUIN_SHELL=bash atuin history start --hook -- "$1" 2>/dev/null)   # line 94
```

* `$( … )` runs a command and stores what it prints, here the new history ID.
* `2>/dev/null` throws away its error messages, so a broken Atuin never clutters the shell; `id` is just empty.
* `ATUIN_SHELL=bash` in front of a command sets that variable for that one command only.

## `local` and `export`

```bash
local id                       # line 93: exists only inside __atuin_preexec
export ATUIN_HISTORY_ID=$id    # line 95: seen by every program started from this shell
```

`id` is gone once the function returns; `ATUIN_HISTORY_ID` lives on until `__atuin_precmd` uses it after the command.

## `declare -p`: what a variable really is

`declare -p name` prints a variable as a line that would recreate it, attributes included:

```console
$ f() { local a=1; export B=2; declare -p a B; }; f
declare -- a="1"
declare -x B="2"
$ declare -p a
bash: declare: a: not found
$ declare -p EPOCHREALTIME
declare -- EPOCHREALTIME="1795054814.086792"
```

```text
declare  -x  B="2"
         │   │ └ value, quoted
         │   └ name
         └ attributes: -- none, -x exported, -a array, -i integer, -r read-only
```

Unlike `echo`, it shows whether a variable exists at all, its attributes, and its exact value. The Bash Debug extension uses it to answer expressions typed in the Debug Console, which is why `id` shows up as `declare -- id="…"`.

## Bonus: Atuin's history IDs are UUIDv7

An ID such as `01a1f18a10b876ba97f5f54166f24eed` starts with a timestamp:

```text
01a1f18a10b8  7 6ba  97f5f54166f24eed
└ ms since 1970   └ version 7, then random bits
```

```console
$ ms=$((16#01a1f18a10b8)); date -d @$((ms/1000))
Thu Nov 19 07:31:59 AM IST 2026
```

Because the time comes first, IDs sort in the order the commands ran.
