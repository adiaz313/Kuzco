# Kuzco — local macOS assistant (v1 release candidate)

Kuzco combines local Llama 3.1 8B, narrow Python tools, voice interaction and an
optional perimeter indicator. Built with Llama. 

## Supported configuration

- Apple Silicon Mac, macOS **14 or later**, 16 GB memory tested. No Intel/Linux/Windows claim.
- Apple Command Line Tools (`xcode-select --install`), including Git, Swift and Clang.
- **uv 0.12.11**; pinned **Python 3.14.7** is managed by uv.
- LM Studio running locally on port 1234, with **Meta Llama 3.1 8B Instruct Q4_K_M**.
- Sherpa keyword spotting, Whisper tiny.en, and Piper northern English male voice.
- Internet for installation and optional DDGS/web retrieval. Inference and audio stay local.

The Llama weights, LM Studio application, voice weights, credentials and personal
data are **not included** in this repository. Read [third-party terms](THIRD_PARTY.md).

## Clone → install → configure → test → run

There is no published repository URL yet. Obtain/clone this candidate repository
from its supplied local path. After publication the same steps start with the
actual GitHub clone URL; do not use an invented URL.

Install [uv 0.12.11](https://docs.astral.sh/uv/getting-started/installation/) from
its official release, then from the cloned folder:

```sh
uv sync --locked --managed-python --group release-test
uv run --locked python configuration.py
uv run --locked python install_assets.py --accept-model-terms
```

The last command explicitly downloads checksum-verified public assets and builds
Whisper and the indicator. It can take several minutes. It does not activate a
microphone or install a background service. No models download during normal use.
Rerunning setup retains your configuration and verifies downloaded files.

**Complete [LM Studio setup](docs/RUNTIME.md) before language requests.** The
corrected template is an explicit runtime requirement, not modified model weights.
Load only the 8B model, start the local server, and verify the template:

```sh
uv run --locked python doctor.py --live --template-config /absolute/path/to/exported-active-template.jinja
uv run --locked --group release-test python -m unittest discover -s tests
uv run --locked python main.py --chat --personality kuzco
```

For the complete voice experience (microphone permission required):

```sh
uv run --locked python main.py --wake --personality kuzco --indicator
```

Say “Kuzco, what time is it?” or “Kuzco, open Calculator.” Green means LISTENING,
purple THINKING, blue SPEAKING; the perimeter clears at IDLE. Ctrl-C exits.
Push-to-talk: replace `--wake` with `--voice`. Text single request:
`uv run --locked python main.py "What time is it?" --personality kuzco`.
Use `--debug` only when you want prompts, evidence and answers visible in Terminal.
Use `--personality default` for neutral responses; `--tts-engine macos` selects
the Daniel fallback if that macOS voice is installed.

## Your data and configuration

Default data root: `~/Library/Application Support/Kuzco`. Override it with
`KUZCO_HOME=/absolute/path` **consistently during setup and launch**, especially
when comparing an existing development installation with this candidate.

| Location under the data root | Purpose |
|---|---|
| `config/kuzco.toml` | Local server port, model ID, background personality, document paths |
| `config/voice_settings.json` | Existing wake and end-of-speech thresholds |
| `config/tts_settings.json` | Piper/Daniel selection; Piper path relative to `assets` or absolute |
| `config/wake_engine.json` | Sherpa default; rejected OpenWakeWord experiment is not installed |
| `config/security_settings.json` | Deterministic tool disable list |
| `assets/` | Downloaded weights, pinned Whisper source/build, indicator binary |
| `kuzco.db` | Explicit personal memory; absent until first use |
| `logs/` | Bounded background and security metadata |

The repository JSON files are inspectable defaults; user overrides win. Restart
after configuration edits. `KUZCO_MEMORY_DB` is an optional legacy database-path
override; unset it for a genuinely fresh installation. No other hidden data is
imported. `documents = []` means no personal RAG collection. Set an absolute list
of `.txt`, `.md`, or `.docx` files in TOML, or use `--docs` in the foreground.
`examples/notes.txt` is explicitly fictional. **Never commit your configuration,
documents, database, recordings or logs.**

No credentials are needed for normal v1 tools. Future trusted integrations must
use `credentials.CredentialStore` and macOS Keychain. Do not put secrets in TOML,
JSON, memory, prompts or environment files. See [security](SECURITY.md).

## Optional background startup

First pass the foreground check. Ensure another Kuzco listener is stopped. Then:

```sh
uv run --locked python service.py install
uv run --locked python service.py status
```

Allow microphone access for **Kuzco Background**. The service captures the clone
and data-root paths during installation and uses that clone's `.venv`; keep both
locations. It follows the selected macOS microphone. After a stale headset
connection, select a working microphone and run `service.py restart`.
`service.py stop` stops it now; `service.py uninstall` removes login startup but
retains all user data. There is one per-user service label and one microphone lock:
installing another clone replaces that user's service, not a parallel assistant.

## Development and limitations

See [architecture](docs/ARCHITECTURE.md), [runtime/template recovery](docs/RUNTIME.md),
[security](SECURITY.md), [contributing](CONTRIBUTING.md),
[license notices](THIRD_PARTY.md), and [Phase 12 report](evaluation/PHASE12_REPORT.md).
The candidate includes bounded Greeting, Timekeeping and Weather Skills, local
audio-device recovery, and conservative web-page extraction. Experimental model
routing and rejected wake-word training artifacts are not part of this candidate.

Source code is offered under GPL-3.0-only; third-party templates, packages,
weights and runtime applications retain their own terms. No model binaries or
prebuilt application bundle are distributed. Do not publish this candidate as
v1 before the remaining quality and redistribution review.
