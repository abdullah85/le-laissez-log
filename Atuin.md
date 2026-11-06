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
