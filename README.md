# Kuzco — Local-First Personal AI Butler

Kuzco v1.0.0 is the first public release of a local-first personal AI assistant and butler for macOS. It combines local model reasoning with deterministic routing, Skills and tools, voice interaction, memory, document retrieval, current information, and security controls.

Built around a local-first architecture, Kuzco keeps inference, memory, documents, speech processing, and assistant logic on your Mac wherever practical while selectively using external sources for capabilities such as current web information and weather.

Kuzco v1.0.0 includes always-on wake-word detection, local speech-to-text and text-to-speech, contextual memory, RAG over local documents, web research with provenance, macOS utilities, weather and timekeeping, configurable personality, visual status indicators, and a deterministic security layer governing tool execution.

Post-v1 development adds [Apple Reminders and lightweight tasks](docs/REMINDERS.md)
through a narrow local EventKit helper. macOS asks for Reminders access on first use.
Timers are deferred.

The first release targets a tested Apple Silicon configuration and keeps the architecture inspectable and modifiable.

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

Clone the [public repository](https://github.com/adiaz313/Kuzco):

```sh
git clone https://github.com/adiaz313/Kuzco.git
cd Kuzco
```

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
when comparing installations.

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

The installed background host also provides a small native [menu-bar status and
master control](docs/MENU_BAR.md). Its switch stops or restores the actual wake
listener; status checks are local and never call Llama.

Post-v1 development adds [bounded Mac control](docs/MAC_CONTROL.md) for volume,
focus, and selected native Apple Music actions. Re-run the asset setup and
reinstall the background service after updating this source; macOS may request
Automation permission for Music. Unsupported Podcasts, artist/album queue,
app-quit, and brightness requests are documented there.

The post-v1 read-only Calendar integration supports explicit requests for
today, tomorrow, and the next event or timed event. It uses a separate signed
EventKit helper and never creates, changes, or removes calendar events. macOS
requires full Calendar permission to read EventKit data even though Kuzco's
helper exposes read operations only. Re-run asset setup after updating, then
allow **Kuzco Calendar** under Privacy & Security → Calendars when prompted.
Calendar details are retrieved only for an explicit request and are not added
to memory, greeting context, ordinary logs, or unrelated model prompts.

Post-v1 Maps/Places support uses a separate signed Apple MapKit helper for
structured place search, explicit ambiguity, route distance/ETA, and opening a
validated route in Apple Maps. See [Maps/Places](docs/MAPS_PLACES.md). Place
search and routing use Apple's network service; Llama remains local. Current
location is requested only for a nearby/current-origin operation and is never
stored in memory or ordinary logs. Re-run asset setup after updating.

The post-v1 [Travel Time Skill](docs/TRAVEL_TIME.md) composes those grounded
MapKit estimates with deterministic time arithmetic and, when explicitly
requested, the existing read-only Calendar integration. It does not retain
location or route history and applies extra time only when the user supplies a
buffer.

The post-v1 [Recommendations Skill](docs/RECOMMENDATIONS.md) selects a small
set of real local MapKit candidates using grounded distance. It does not invent
ratings, hours, prices, reviews, or menu details and stores no recommendation
or location history.

## Development and limitations

See [architecture](docs/ARCHITECTURE.md), [runtime/template recovery](docs/RUNTIME.md),
[security](SECURITY.md), [contributing](CONTRIBUTING.md),
[license notices](THIRD_PARTY.md), and [Phase 12 report](evaluation/PHASE12_REPORT.md).
Kuzco includes bounded Greeting, Timekeeping and Weather Skills, local
audio-device recovery, and conservative web-page extraction. Experimental model
routing and rejected wake-word training artifacts are not part of v1.0.0.

Source code is offered under GPL-3.0-only; third-party templates, packages,
weights and runtime applications retain their own terms. No model binaries or
prebuilt application bundle are distributed. Llama-backed conversation can be
slower than direct tasks; occasional explanation and web-evidence errors and
retrieval-context delays remain known v1 limitations.
