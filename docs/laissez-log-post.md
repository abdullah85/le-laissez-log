*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

Le Laissez-Log is a small **terminal-session watcher for [ActivityWatch](https://github.com/ActivityWatch/activitywatch)**, the open-source, local-first time tracker. ActivityWatch already knows *when* you are at the keyboard (`aw-watcher-afk`) and *which window* is active (`aw-watcher-window`). What it doesn't know is **what you actually did in the terminal**, which is where a lot of daily learning happens: the commands you tried, the errors you hit, the fix that finally worked.

My watcher wraps your shell in a PTY and writes one ActivityWatch event per command: the command, how long it ran, and a short, redacted snippet of its output. You keep working as usual. The log builds itself in the background, so at the end of the day there is a searchable record of what you learned, with no note-taking.

The lazy part: no habit to maintain, no notes to write. You work and it records.

## Demo

<!-- TODO: add a screen recording or GIF: run the wrapper, type a few commands, then show the events with the curl command below. -->

Run it against a throwaway `aw-server --testing` instance, then read the events back:

```bash
python aw_watcher_terminal.py --testing
# ...type a few commands, then exit...
curl -s "localhost:5666/api/0/buckets/aw-watcher-terminal_$(hostname)/events" | jq -c '.[] | {timestamp, duration, data}'
```

The shape of an event (illustrative values):

```json
{
  "timestamp": "2026-10-26T06:35:46+00:00",
  "duration": 0.4,
  "data": {
    "cmd": "echo hello token=<redacted>",
    "approx": false,
    "output_bytes": 84,
    "output_head": "hello token=<redacted>\n"
  }
}
```

## Code

<!-- TODO: replace with your repo link, then use the embed tag on its own line:
{% embed https://github.com/<you>/le-laissez-log %}
-->

The whole watcher is a single file, `aw_watcher_terminal.py`, built on `aw-client`.

## How I Built It

**Learning the system first.** Before writing anything, I ran `aw-server`, `aw-watcher-afk` and `aw-watcher-window` separately instead of using the bundled tray launcher, and poked at the REST API with `curl`. A few things became clear:

- Everything is **events inside buckets**. The server doesn't know what the data means, so meaning is applied at query time.
- Watchers don't write an event per poll. They send **heartbeats**. If the data is identical and arrives within `pulsetime` of the last event's end, the server *extends* that event. Otherwise it starts a new one. I confirmed this by creating my own bucket in IPython and sending heartbeats by hand.

**The watcher.** There is no official watcher for terminal content (the existing `aw-watcher-input` counts keypresses only, by design). So I built one:

- It runs your `$SHELL` inside a PTY, relays bytes both ways, and rebuilds each command from keystrokes.
- It writes events with `client.insert_event`. Each command is a discrete event rather than a heartbeat, and the event is written once the shell prompt has returned and output has settled.

**Privacy decisions that shaped the design.** A terminal recorder is sensitive by nature, so I made a few choices on purpose:

- **One session, not a global keylogger.** A system-wide key hook would see every app. A PTY wrapper sees only the session it wraps.
- **Record only when the shell owns the terminal.** Keystrokes count only while the shell is the foreground process. That means password prompts (`sudo`, `ssh`), editors, pagers and REPLs are never stored. I used `tcgetpgrp` on the PTY to tell the difference.
- **Redaction and truncation.** `password=`, `token=`, `api_key=` patterns are redacted, and output is cut to 500 bytes by default.
- **Everything stays local.** The data goes into ActivityWatch's own SQLite database on your machine.

**Bugs I hit along the way.** My first password-prompt check looked at terminal echo flags and discarded every command, because readline turns echo off at a normal prompt too. Later, events were written one command late, and pasted text leaked bracketed-paste codes into commands. Fixing these led to the foreground-process approach.

**AI use.** The watcher has no model at runtime. I used an AI coding assistant (Claude) as a pair programmer while building and debugging it.

## Why Does Open Innovation Matter?

Because the thing I wanted to build is something a closed service wouldn't let me build.

- **I could read how it works.** Understanding heartbeat merging came from the open API and open source, not from a vendor's documentation of a black box.
- **I could extend it.** ActivityWatch has an open REST API and a client library, so a watcher for a data source nobody had covered was an afternoon of work.
- **The data stays mine.** Command history and output are about as personal as data gets. With an open, local-first tool I can inspect the database, set the retention, and delete it. With a closed cloud tracker, I'd be trusting a company with my terminal.
- **It leaves room for local AI.** Because the log lives in an open local store, a locally run model could later summarize "what I learned today" without any of it leaving my machine. That's not built yet, but it's the direction this opens.

## The Lazy Payoff

I ran it on my own machine while building this post, and it recorded real sessions: `ls`, `man` pages, pastes and `exit`. The payoff I care about isn't a number of minutes saved. It's that I no longer have to remember to write down what I tried. The terminal history I'd normally lose is now an event stream I can query by day.
