# Phase 13 Release-Candidate Finalization

Status: product freeze complete; publication candidate prepared.

## Artifact

The publication candidate is this repository. It contains the Phase 13 Weather, Greeting, Timekeeping, indicator, document, web, audio resilience, security, and regression changes that were dogfooded in the active release candidate. Personal runtime state is excluded.

## Privacy and reproducibility

- The public tree contains no personal documents, databases, credentials, transcripts, recordings, logs, virtual environments, model binaries, or developer-machine paths.
- The private dogfooding document remains local user data and is not required by a fresh install.
- The public document fixture is synthetic and exercises generic document analysis.
- The repository history was rebuilt as a clean publication history so removed private-derived fixtures are not retained in reachable commits.
- A fresh environment created by the documented `uv sync --locked --managed-python --group release-test` path initialized an empty document configuration and passed the complete suite.

## Validation

The clean release tree passes the full automated suite: 304 tests.

`pip-audit` reported no known vulnerabilities for the locked environment. Static review found only previously reviewed intentional subprocess/process-launch findings in local audio, indicator, weather, and web helpers; no new actionable issue was identified. Semgrep Community Edition is not installed in the release environment and remains a documented optional review tool.

The active dogfooded RC validated conversation, deterministic time, weather, current web, document/RAG, memory, application launch, Sherpa wake, Whisper STT, Piper TTS, visual states, and audio-device recovery. The clean tree is source-equivalent apart from publication-safe fixtures and empty fresh-user state.

## Known v1 limitations

Llama-backed conversation can be slower than deterministic paths, and occasional explanation or web-evidence quality limitations remain documented for later work. Runtime setup still requires macOS permissions, LM Studio with the documented Llama 3.1 8B configuration, and the local voice assets described in the runtime documentation.

