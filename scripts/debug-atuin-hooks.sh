#!/usr/bin/env bash
# Runs Atuin's bash hooks for one command, so they can be stepped through with the
# "atuin bash hooks (.atuin-output)" launch config. Set breakpoints in
# vendor/atuin/crates/atuin/src/shell/atuin.bash, e.g. in __atuin_preexec and __atuin_precmd.
#
# In a real shell, bash-preexec calls the hooks; here they are called by hand.

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
. "$root/.venv/bin/activate"
. "$root/vendor/atuin/crates/atuin/src/shell/atuin.bash"

# Act as if pty-proxy owns the terminal, so the hooks print the output markers.
__atuin_pty_proxy_owns_tty=1
ATUIN_PTY_PROXY_ACTIVE=2

cmd=${1:-echo debug-hooks-test}
__atuin_preexec "$cmd"   # atuin history start, then the C marker
eval "$cmd"
__atuin_precmd           # D marker, then atuin history end
