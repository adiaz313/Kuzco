# Kuzco security boundary

LLMs propose. Trusted Python authorizes. Narrow tools execute.

## Authority

`security_policy.py` owns the immutable tool/risk registry, argument validation and EXECUTE / CONFIRM / DENY decisions. `security_settings.json` can disable tools; it cannot add tools or lower their risk. Invalid configuration fails closed. `main.execute_tool` checks policy before dispatch, and tool helpers also check policy so internal research calls respect disabled tools. Explicit memory commands pass through policy in `MemoryStore.operate`.

The application entry points establish the actual current request in a scoped context variable. The model, Skill instructions, source text and conversation history cannot replace it or supply permission metadata. App launching requires a named action in that current request. Negation, quoted examples and ambiguous “open it” references are conservatively rejected; naming the app directly remains frictionless. Explicit single-record memory operations are parsed from user input, never inferred from LLM output. Memory is not an LLM tool.

This is an application boundary, not a Python sandbox. Installed code, local configuration and the logged-in macOS account are trusted. A malicious same-account process or modified Python code can bypass application functions; this phase does not claim otherwise. Physical/spoofed voice input is also not identity authentication. Model answers can still be wrong or influenced by source text, but source text cannot add capabilities or manufacture a grant.

## Current risk classes

| Risk | Current actions |
|---|---|
| READ_ONLY | Time, document search, web search, webpage reading, research, memory recall |
| LOCAL_ACTION | Named application launch; explicit remember/update/forget of bounded personal memory records |
| EXTERNAL_ACTION | No production tool; future registered actions require trusted confirmation |
| SENSITIVE_DESTRUCTIVE | No production tool; denied by the v1 policy |

Web retrieval is READ_ONLY despite making network requests: it does not post, purchase, authenticate or change external state. “Forget” targets one uniquely identified memory record; it is not arbitrary file deletion. No shell, arbitrary SQL, browser automation or general filesystem tool exists.

## Confirmation

`Confirmations` is a trusted-code interface, not a tool. Requests create bounded, expiring, one-use tickets tied to exact action arguments. Only a future trusted interaction handler may record approval. `execute` reevaluates current policy and consumes the matching grant before executing. A JSON `confirmed: true`, a model claim of consent, or an unknown ticket grants nothing. No current tool requires an extra confirmation prompt, and no dangerous demonstration capability or confirmation UI was added.

## Credentials

The locked installation includes Keyring. `CredentialStore` explicitly selects `keyring.backends.macOS.Keyring` and scopes entries to `local.kuzco.credentials.v1`. Automatic backend selection and plaintext fallback are absent. Missing entries return `None`; failures return generic errors without secret values. Returned `Secret` objects have a redacted representation. Only trusted future integration code may call `.reveal()` at an authenticated API boundary. Never put the revealed string in tool results, prompts, debug logs, config or memory.

No credential tool or authenticated integration is exposed. Personal memory rejects labeled credential requests and non-string secret objects. This is not a universal secret detector for arbitrary text a user voluntarily types. Keychain access follows macOS account/executable permissions; it does not isolate hostile Python code running under the same account. No custom encryption was implemented.

Ordinary tests mock the backend and require no real credential or permission dialog. Existing Keychain entries are OS-account state and are never exported into this repository. A different `KUZCO_HOME` isolates memory/configuration, not the macOS Keychain namespace; it is not a separate security identity.

## Observability

`logs/security.jsonl` under the configured data root holds timestamp, registered action, risk, decision and outcome only. No arguments, user requests, result bodies, tickets, credentials or exception strings are accepted by the logger. Unknown names become `unknown`. Files use mode 0600 and rotate at 128 KiB with two backups. Audit storage failure cannot authorize an action or crash the assistant; recording is best effort. Foreground `--debug` remains an explicit content-inspection mode, so do not share its output without reviewing private source content. The credential interface itself emits no values there.

## Small development checks

Keep audit tools outside the voice runtime:

```sh
UV_PROJECT_ENVIRONMENT=.security-venv uv sync --locked --only-group security
.security-venv/bin/pip-audit --path .venv/lib/python3.14/site-packages --progress-spinner off --timeout 10
.security-venv/bin/bandit -r . -x ./.venv,./.security-venv,./tests -ll
uv run --locked --group release-test python -m unittest discover -s tests
```

`pip-audit` sends package names/versions to PyPI advisory services; Bandit scans locally. Neither command is a runtime assistant capability. Review findings rather than suppressing them or claiming an entirely clean scan. Pip auditing does not cover model weights, macOS frameworks, bundled native binaries or all possible vulnerabilities. Locked dependencies do not make those components automatically secure.

See [release validation](evaluation/PHASE12_REPORT.md). The Phase 11 security architecture is preserved.
