#!/usr/bin/env python3
"""aw-watcher-terminal: record commands typed in ONE terminal session, plus a
bounded snippet of their output, as events in an ActivityWatch bucket.

How it works: it runs your shell inside a PTY and relays bytes both ways.
Only this session is observed. Nothing else on the system is hooked.

Privacy defaults:
  * Input typed at password prompts (ECHO off while the line discipline is
    still canonical, e.g. sudo/ssh) is never stored, and neither is input
    typed inside full-screen apps (vim, less, htop).
  * Obvious secrets (password=..., token=..., api_key=...) are redacted.
  * Output is truncated (--max-output bytes, 0 disables output capture).

Limits (be honest about them in your write-up):
  * Commands are rebuilt from keystrokes. History recall (arrow keys) and tab
    completion can't be reconstructed, so those events get approx=true.
  * Output includes the prompt of the next line; ANSI codes are stripped.

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

from aw_client import ActivityWatchClient
from aw_core.models import Event

ANSI = re.compile(rb"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\x1b[@-Z\\-_]")
SECRET = re.compile(r"(?i)\b(pass(word|wd)?|token|secret|api[_-]?key)=\S+")


def clean_output(raw: bytes, limit: int) -> str:
    text = ANSI.sub(b"", raw).replace(b"\r", b"").decode("utf-8", "replace")
    lines = text.split("\n", 1)            # first line is the echoed command
    body = lines[1] if len(lines) > 1 else ""
    return SECRET.sub(r"\1=<redacted>", body)[:limit]


def main():
    ap = argparse.ArgumentParser(description="ActivityWatch terminal-session watcher")
    ap.add_argument("--testing", action="store_true", help="use aw-server --testing (port 5666)")
    ap.add_argument("--max-output", type=int, default=500, help="bytes of output kept per command (0 = none)")
    ap.add_argument("--shell", default=os.environ.get("SHELL", "/bin/bash"))
    args = ap.parse_args()

    client = ActivityWatchClient("aw-watcher-terminal", testing=args.testing)
    bucket = f"aw-watcher-terminal_{client.client_hostname}"
    client.create_bucket(bucket, event_type="app.terminal.command")

    pid, master = pty.fork()
    if pid == 0:
        os.execvp(args.shell, [args.shell])

    fd_in = sys.stdin.fileno()

    def sync_size(*_):
        size = fcntl.ioctl(fd_in, termios.TIOCGWINSZ, b"\0" * 8)
        fcntl.ioctl(master, termios.TIOCSWINSZ, size)

    sync_size()
    signal.signal(signal.SIGWINCH, sync_size)

    line = bytearray()      # keystrokes of the line being typed
    approx = False          # saw escape/tab, so line may not equal real command
    pending = None          # command awaiting its output
    out = bytearray()       # raw output since the pending command started
    out_bytes = 0
    last_out = time.time()
    alt_screen = False      # True while a full-screen app (vim, less) is running

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
                ready, _, _ = select.select([fd_in, master], [], [])
            except InterruptedError:
                continue
            if fd_in in ready:
                data = os.read(fd_in, 1024)
                os.write(master, data)      # shell always gets the input
                lflag = termios.tcgetattr(master)[3]
                # readline prompts: ECHO off + ICANON off (record).
                # password prompts: ECHO off + ICANON on (never record).
                # full-screen apps (vim, less): ignored via alt-screen flag.
                recordable = not alt_screen and (
                    bool(lflag & termios.ECHO) or not (lflag & termios.ICANON))
                for b in data:
                    if not recordable:
                        line.clear()        # password prompt: store nothing
                    elif b in (13, 10):
                        finalize()
                        cmd = SECRET.sub(r"\1=<redacted>", line.decode("utf-8", "replace")).strip()
                        if cmd:
                            pending = {"t": time.time(), "cmd": cmd, "approx": approx}
                        line.clear(); approx = False
                    elif b in (127, 8):
                        if line:
                            line.pop()
                    elif b in (9, 27):
                        approx = True
                    elif b >= 32:
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
                if b"\x1b[?1049h" in data or b"\x1b[?47h" in data:
                    alt_screen = True
                if b"\x1b[?1049l" in data or b"\x1b[?47l" in data:
                    alt_screen = False
                if pending is not None:
                    out_bytes += len(data)
                    if len(out) < args.max_output * 4:      # cap memory; trim later
                        out += data
    finally:
        termios.tcsetattr(fd_in, termios.TCSADRAIN, old)
        finalize()
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass


if __name__ == "__main__":
    main()    
