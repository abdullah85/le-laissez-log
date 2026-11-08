# rcfile for `make atuin-trial`: your usual shell, plus the venv and Atuin.
[ -f ~/.bashrc ] && . ~/.bashrc
. .venv/bin/activate
eval "$(atuin init bash)"
