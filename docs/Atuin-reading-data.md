# Reading data from `.atuin-output`

Commands for getting history, captured output and logs out of the capture shell's store (`make atuin-output`). Run them from the repo root. See [Atuin.md](Atuin.md) for what each store is.

## Setup

```bash
export ATUIN_HOME=$PWD/.atuin-output ATUIN_OUTPUT__ENABLED=true \
       ATUIN_DAEMON__ENABLED=true ATUIN_DAEMON__AUTOSTART=true
```

Output search goes through the daemon. Without the two `DAEMON` variables it fails with "could not connect to the daemon".

## Commands (`history.db`)

A plain SQLite table. Times are in nanoseconds.

```bash
# Latest commands with time, exit code and duration
sqlite3 -readonly -box .atuin-output/data/history.db \
  "select id, datetime(timestamp/1e9,'unixepoch','localtime') t, exit, duration/1e6 ms, command
   from history where deleted_at is null order by timestamp desc limit 20"

# Failed commands only
sqlite3 -readonly -box .atuin-output/data/history.db \
  "select datetime(timestamp/1e9,'unixepoch','localtime') t, exit, command from history where exit != 0"

# Everything as JSON or CSV
sqlite3 -readonly -json .atuin-output/data/history.db "select * from history" > history.json
sqlite3 -readonly -csv -header .atuin-output/data/history.db "select * from history" > history.csv
```

## Captured output

Only through Atuin; the files on disk are an internal binary format.

```bash
# Full output of matches, as JSON (id, command, cwd, exit, duration_ns, output)
.venv/bin/atuin output search --style json --limit 50 capture

# Only the matching lines, with 2 lines of context
.venv/bin/atuin output search -C 2 --style plain capture

# One match per line, for piping
.venv/bin/atuin output search --style ndjson --limit 100 exit
```

* Search always needs at least one word, so there is no "dump all". `--limit` defaults to 5.
* Each result's `id` matches `history.id` in `history.db`.

## Search index and logs

```bash
# How many commands have searchable output
sqlite3 -readonly .atuin-output/data/output-capture-index-2.sqlite "select count(*) from indexed"

# Daemon and search logs (one file per day)
tail -n 50 .atuin-output/logs/daemon.log.$(date +%F)
grep -i error .atuin-output/logs/*.log.*
```

## Afterwards

The output search starts a daemon in the background. Stop it with:

```bash
.venv/bin/atuin daemon stop
```
