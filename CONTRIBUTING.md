# Contributing

Use the README setup and locked Python environment. Keep patches small. Preserve
the deterministic policy boundary, loopback inference, explicit memory semantics,
bounded retrieval and existing audio behavior. Do not introduce cloud AI or tools
as incidental dependencies. Do not change the lockfile during ordinary execution.

Run `uv run --locked --group release-test python -m unittest discover -s tests`.
Tests use synthetic fixtures and mocks, no live microphone/network. For a fully
isolated run set `KUZCO_HOME` to a temporary directory and unset `KUZCO_MEMORY_DB`.
Native, Keychain and network smoke checks are separate and explicitly invoked.

Security tools can be installed into a separate environment with
`UV_PROJECT_ENVIRONMENT=.security-venv uv sync --locked --only-group security`.
Then run `.security-venv/bin/pip-audit --path .venv/lib/python3.14/site-packages`
and `.security-venv/bin/bandit -r . -x .venv,.security-venv,tests -ll`.
Do not blindly upgrade packages to silence findings. Record applicability.

Only intentional source, defaults, tests and public documentation belong in Git.
Never add recordings, credentials, private documents, SQLite files, local settings,
model binaries or raw personal debug traces. Report security issues privately
to the project maintainer; no public private-log dump. A public reporting address
will be established before publication, not invented for this private candidate.

This candidate has no upstream Git history or public remote. Local release
construction commits are not a v1 tag. Publication requires a separate decision.
