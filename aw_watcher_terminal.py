#!/usr/bin/env python3
"""aw-watcher-terminal: record commands typed in ONE terminal session, plus a
bounded snippet of their output, as events in an ActivityWatch bucket.

How it works: it runs your shell inside a PTY and relays bytes both ways.
Only this session is observed. Nothing else on the system is hooked.

Recording rules:
  * Keystrokes are recorded only while the shell itself owns the terminal
    (foreground process group == the shell). So input typed into sudo/ssh
    password prompts, vim, less/man, python REPLs etc. is never stored.
  * `read -s` style prompts (ECHO off, canonical mode on) are also skipped.
  * Obvious secrets (password=..., token=..., api_key=...) are redacted.
  * Output is truncated (--max-output bytes; 0 disables output capture).
  * An event is written as soon as the shell prompt returns and output has been
    quiet for --settle seconds (or when the session ends).

Limits (be honest about them in your write-up):
  * Commands are rebuilt from keystrokes. History recall (arrow keys) and tab
    completion can't be reconstructed, so those events get approx=true.
  * Output includes everything the command printed, minus the echoed command
    line and the trailing prompt; ANSI codes are stripped.

Usage:  python aw_watcher_terminal.py --testing
"""
import argparse
import fcntl
import os
import pty
import re
import select
import signal
import sys
import termios
import time
import tty
from datetime import datetime, timezone

import requests
from aw_client import ActivityWatchClient
from aw_core.models import Event

ANSI = re.compile(
    rb"\x1b\[[0-9;?<>=]*[ -/]*[@-~]"      # CSI sequences (colors, cursor, modes)
    rb"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC (window title etc.)
    rb"|\x1b[()][A-Za-z0-9]"                # charset selection
    rb"|\x1b[=>78DEHMNOZc]"                 # keypad mode, save/restore cursor, etc.
)
SECRET = re.compile(r"(?i)\b(pass(word|wd)?|token|secret|api[_-]?key)=\S+")


def redact(text: str) -> str:
    return SECRET.sub(r"\1=<redacted>", text)


def clean_output(raw: bytes, limit: int) -> str:
    text = ANSI.sub(b"", raw).replace(b"\r", b"").decode("utf-8", "replace")
    parts = text.split("\n", 1)             # first line is the echoed command
    body = parts[1] if len(parts) > 1 else ""
    if body and not body.endswith("\n"):    # trailing partial line = next prompt
        body = body.rsplit("\n", 1)[0] + "\n" if "\n" in body else ""
    return redact(body)[:limit]


def main():
    ap = argparse.ArgumentParser(description="ActivityWatch terminal-session watcher")
    ap.add_argument("--testing", action="store_true", help="use aw-server --testing (port 5666)")
    ap.add_argument("--max-output", type=int, default=500, help="bytes of output kept per command (0 = none)")
    ap.add_argument("--settle", type=float, default=0.3, help="seconds of quiet at the prompt before an event is written")
    ap.add_argument("--shell", default=os.environ.get("SHELL", "/bin/bash"))
    ap.add_argument("--debug", metavar="FILE", help="log terminal state per input chunk (no keystrokes)")
    args = ap.parse_args()

    client = ActivityWatchClient("aw-watcher-terminal", testing=args.testing)
    bucket = f"aw-watcher-terminal_{client.client_hostname}"
    try:
        client.create_bucket(bucket, event_type="app.terminal.command")
    except requests.exceptions.ConnectionError:
        port = 5666 if args.testing else 5600
        sys.exit(f"Could not reach aw-server on localhost:{port}.\n"
                 f"Start it first ('aw-server{' --testing' if args.testing else ''}'), "
                 f"and make sure --testing matches how the server was started.")

    pid, master = pty.fork()
    if pid == 0:
        os.execvp(args.shell, [args.shell])

    fd_in = sys.stdin.fileno()

    def sync_size(*_):
        size = fcntl.ioctl(fd_in, termios.TIOCGWINSZ, b"\0" * 8)
        fcntl.ioctl(master, termios.TIOCSWINSZ, size)

    def shell_in_foreground() -> bool:
        try:
            return os.tcgetpgrp(master) == pid
        except OSError:
            return True

    sync_size()
    signal.signal(signal.SIGWINCH, sync_size)

    line = bytearray()      # keystrokes of the line being typed
    approx = False          # history/tab/arrow keys seen: line may not equal the real command
    esc = None              # None | "esc" | "csi" | "ss3": escape-sequence parser state
    csi = bytearray()
    in_paste = False        # inside a bracketed paste (newlines are text, not Enter)
    pending = None          # command awaiting its output
    out = bytearray()
    out_bytes = 0
    last_out = time.time()

    def finalize():
        nonlocal pending, out, out_bytes
        if pending is None:
            return
        dur = max(0.0, last_out - pending["t"])
        data = {"cmd": pending["cmd"], "approx": pending["approx"], "output_bytes": out_bytes}
        if args.max_output:
            data["output_head"] = clean_output(bytes(out), args.max_output)
        ts = datetime.fromtimestamp(pending["t"], tz=timezone.utc)
        client.insert_event(bucket, Event(timestamp=ts, duration=dur, data=data))
        pending, out, out_bytes = None, bytearray(), 0

    old = termios.tcgetattr(fd_in)
    try:
        tty.setraw(fd_in)
        while True:
            try:
                ready, _, _ = select.select([fd_in, master], [], [], 0.1 if pending else None)
            except InterruptedError:
                continue

            if fd_in in ready:
                data = os.read(fd_in, 1024)
                os.write(master, data)              # the shell always gets the input
                lflag = termios.tcgetattr(master)[3]
                fg = shell_in_foreground()
                # ECHO off + ICANON off = readline at the prompt (record).
                # ECHO off + ICANON on  = password-style prompt (never record).
                recordable = fg and (bool(lflag & termios.ECHO) or not (lflag & termios.ICANON))
                if args.debug:
                    with open(args.debug, "a") as dbg:
                        dbg.write(f"{time.time():.3f} nbytes={len(data)} shell_fg={fg} "
                                  f"echo={bool(lflag & termios.ECHO)} "
                                  f"icanon={bool(lflag & termios.ICANON)} recordable={recordable}\n")
                if not recordable:
                    line.clear(); esc = None; in_paste = False
                else:
                    for b in data:
                        if esc == "esc":
                            if b == ord("["):
                                esc, csi = "csi", bytearray()
                            elif b == ord("O"):
                                esc = "ss3"
                            else:
                                esc = None; approx = True
                            continue
                        if esc == "csi":
                            csi.append(b)
                            if 0x40 <= b <= 0x7e:           # final byte
                                seq, esc = bytes(csi), None
                                if seq == b"200~":
                                    in_paste = True
                                elif seq == b"201~":
                                    in_paste = False
                                else:
                                    approx = True           # arrows, home/end, ...
                            continue
                        if esc == "ss3":
                            esc = None; approx = True
                            continue
                        if b == 27:
                            esc = "esc"
                        elif in_paste and b in (10, 13):
                            line.append(10)                 # pasted newline is text
                        elif b in (13, 10):
                            finalize()
                            cmd = redact(line.decode("utf-8", "replace")).strip()
                            if cmd:
                                pending = {"t": time.time(), "cmd": cmd, "approx": approx}
                            line.clear(); approx = False
                        elif b in (127, 8):
                            if line:
                                line.pop()
                        elif b == 9:
                            approx = True
                        elif b >= 32 or (in_paste and b == 9):
                            line.append(b)
            if master in ready:
                try:
                    data = os.read(master, 4096)
                except OSError:
                    break
                if not data:
                    break
                os.write(sys.stdout.fileno(), data)
                last_out = time.time()
                if pending is not None:
                    out_bytes += len(data)
                    if len(out) < args.max_output * 4:      # cap memory; trimmed later
                        out += data

            # Write the event once the prompt is back and output has settled.
            # This runs after reading I/O: the shell regains the terminal just
            # before it prints its prompt, so checking earlier would lose it.
            if (pending is not None and last_out > pending["t"]
                    and time.time() - last_out > args.settle and shell_in_foreground()):
                finalize()
    finally:
        termios.tcsetattr(fd_in, termios.TCSADRAIN, old)
        finalize()
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass


if __name__ == "__main__":
    main()
