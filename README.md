# Kuzco — local-first personal AI butler for macOS

Kuzco v1.5.0 is an inspectable personal assistant for Apple Silicon Macs. It
combines deterministic Python Skills, narrow native macOS integrations, and a
local Llama 3.1 8B model. Common tasks such as time, greetings, reminders,
calendar queries, volume, Maps routes, and recommendations use structured code
and native data. Llama handles conversation, interpretation, and synthesis when
those tasks genuinely require language reasoning.

Kuzco is **local-first**, not fully offline. Llama inference, wake detection,
speech recognition, speech output, memory, document retrieval, policy, and
assistant logic run locally. Weather, DDGS search/web reading, and Apple
MapKit/Places require network access. Calendar, Reminders, Music, location, and
audio controls use permission-controlled macOS services.

## What v1.5.0 supports

- “Kuzco” wake listening with Sherpa, local Whisper STT, and local Piper TTS
  (Daniel is an optional macOS fallback).
- Kuzco and neutral personalities, interactive text/chat, push-to-talk, and the
  green/purple/blue LISTENING/THINKING/SPEAKING perimeter indicator.
- Fast deterministic greetings, local time/date, and current weather.
- DDGS web search, bounded webpage reading, and multi-source answers with source
  metadata; external content remains untrusted data.
- RAG over a user-configured small collection of `.txt`, `.md`, or `.docx`
  files. No personal document ships with the project.
- Explicit SQLite memory: remember, recall, update, and forget bounded facts.
- Apple Reminders: list, create, complete, and uniquely remove reminders/tasks.
- Bounded Mac controls: open/focus named apps, set/adjust/mute output volume,
  and selected Apple Music transport, song, and playlist operations.
- Read-only Calendar queries and schedule summaries.
- Apple MapKit place lookup, directions, route distance/time, calendar-aware
  travel calculations, and grounded nearby recommendations.
- A signed menu-bar host with runtime/wake/model status, a real master enable
  switch, login startup, and clean quit.

Kuzco does not expose shell commands, arbitrary AppleScript or Shortcuts,
browser automation, file deletion, keyboard/mouse automation, Calendar writes,
or unrestricted computer control. Apple Podcasts control, display brightness,
timers, and a Kuzco-owned notification subsystem are not currently supported.

## Architecture and trust boundary

```text
user → wake/text input → deterministic routing/Skills
     → grounded tools and native integrations → security policy
     → Llama only where interpretation is useful → grounded response
     → local speech output
```

**Deterministic when possible; Llama when intelligence is required.** Llama is
not the factual authority for time, weather observations, Calendar, Reminders,
Maps, routes, travel estimates, application state, or menu lifecycle.

Every relevant tool action passes through trusted policy code:

```text
LLM/Skill proposes → policy authorizes → narrow tool executes
```

Retrieved web/document text, model output, personality instructions, and Skill
instructions cannot grant permissions. See [architecture](docs/ARCHITECTURE.md)
and [security](SECURITY.md).

## Tested configuration

- Apple Silicon Mac; macOS 14 or later. Development validation used an M1 Mac
  with 16 GB unified memory. Intel, Linux, and Windows are unsupported.
- Apple Command Line Tools, including Git, Swift, and Clang.
- [uv](https://docs.astral.sh/uv/) **0.12.11** and uv-managed Python **3.14.7**.
- LM Studio on loopback port 1234.
- `lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF`, file
  `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`.
- The versioned corrected prompt template in `runtime/llama31.jinja`.

The repository does not contain Llama weights, LM Studio, voice/wake/STT weights,
credentials, compiled app bundles, or personal data. Review [third-party terms](THIRD_PARTY.md).

## Install

Clone the public repository and install the locked environment:

```sh
git clone https://github.com/adiaz313/Kuzco.git
cd Kuzco
uv sync --locked --managed-python --group release-test
uv run --locked python configuration.py
uv run --locked python install_assets.py --accept-model-terms
```

Asset setup downloads checksum-verified public voice/wake/STT assets, builds
Whisper and the native helpers, and may take several minutes. It does not start
the microphone or install the login service. Review the Sherpa/Piper model terms
before accepting them.

### LM Studio setup

Follow [the exact runtime instructions](docs/RUNTIME.md). In summary:

1. Install the named Q4_K_M model and use identifier
   `meta-llama-3.1-8b-instruct`.
2. In that model’s Jinja prompt-template setting, paste the complete contents of
   `runtime/llama31.jinja`, save it for the model, and reload it.
3. Bind LM Studio’s local API only to `localhost:1234`; keep CORS and verbose
   request logging off and content redaction on.
4. Export the active template and verify it:

```sh
uv run --locked python doctor.py --live \
  --template-config /absolute/path/to/exported-active-template.jinja
```

This explicit template correction is required; an untouched stock template is
not the validated configuration. No model weights are modified.

### Configure and test

Kuzco’s default data root is `~/Library/Application Support/Kuzco`. Override it
with `KUZCO_HOME=/absolute/path` consistently during setup and launch.

| Data-root location | Purpose |
|---|---|
| `config/kuzco.toml` | model, port, personality, and document paths |
| `config/voice_settings.json` | wake and endpoint thresholds |
| `config/tts_settings.json` | Piper/Daniel choice and voice path |
| `config/wake_engine.json` | Sherpa wake configuration |
| `config/security_settings.json` | tool-disable settings |
| `assets/` | downloaded/built local runtime assets |
| `kuzco.db` | explicit memory, created only when used |
| `logs/` | bounded lifecycle/security metadata |

`documents = []` is the clean default. Add absolute paths to your own `.txt`,
`.md`, or `.docx` files. Never commit your data directory, private configuration,
documents, database, recordings, or logs.

Run the complete test suite:

```sh
uv run --locked --group release-test python -m unittest discover -s tests
```

## Run Kuzco

Text chat:

```sh
uv run --locked python main.py --chat --personality kuzco
```

Push-to-talk or wake mode:

```sh
uv run --locked python main.py --voice --personality kuzco
uv run --locked python main.py --wake --personality kuzco --indicator
```

Allow microphone access when macOS asks. Only final human-facing responses are
spoken. Add `--debug` only when you intentionally want prompts and evidence in
Terminal; review debug output before sharing it.

### Background service and menu bar

After foreground voice mode works:

```sh
uv run --locked python service.py install
uv run --locked python service.py status
```

The signed **Kuzco Background** host runs at login and follows the selected macOS
microphone. macOS may separately request Calendar, Reminders, Location, and Music
Automation permission when those capabilities are first used.

The menu reports:

- **Kuzco:** Running, Paused, or Not Running.
- **Wake Word:** On or Off.
- **Local Model:** **Available** in green when LM Studio can reach the configured
  model; **Unavailable** in red otherwise. Loaded versus idle is intentionally
  not exposed.
- **Kuzco Enabled:** stops or restores the actual assistant/wake listener. It
  does not stop or unload LM Studio.
- **Quit Kuzco:** cleanly stops the host for the current login session.

Use `service.py restart` after changing configuration or recovering from a stale
audio-device handoff. Use `service.py start` after Quit, and `service.py uninstall`
to remove login startup while retaining user data. See [menu details](docs/MENU_BAR.md).

## Permissions and network use

| Capability | Permission/service |
|---|---|
| Wake/STT | Microphone; audio remains local |
| Calendar | Full Calendar permission required by EventKit; Kuzco reads only |
| Reminders | Reminders full access for the bounded supported actions |
| Apple Music | Automation permission when native playback is requested |
| Weather/Maps/Places/routes | Location when needed; Apple/network provider |
| Web research | DDGS and selected public HTTP(S) pages |

Current location and Calendar locations are purpose-limited to the active task
and are not added to memory or ordinary logs. Web queries send only the minimum
query needed; full conversation history, documents, memory, personality, and
system prompts are not sent to DDGS.

## Known limitations

- Installation is technical and requires manual LM Studio/model/template and
  macOS permission setup.
- Llama-backed conversation and synthesis are slower than deterministic Skills
  and can still make mistakes; grounded evidence should be treated accordingly.
- DDGS and public pages can fail, rate-limit, or provide incomplete snippets.
- MapKit, weather, and route availability vary by network and region; estimates
  are not guarantees, and ratings are not available through the current adapter.
- Named Music playback is limited to uniquely matched content in the user’s
  native library. Output devices may not expose writable system volume.
- The source distribution downloads runtime model assets separately; their
  upstream licenses remain distinct from Kuzco’s GPL source license.

See [release notes](RELEASE_NOTES_v1.5.0.md), [contributing](CONTRIBUTING.md),
[license](LICENSE), and [third-party notices](THIRD_PARTY.md).
