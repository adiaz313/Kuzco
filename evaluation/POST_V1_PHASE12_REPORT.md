# Post-v1 Phase 12 — v1.5.0 Release Engineering

Status: **12A COMPLETE; 12B SOAK IN PROGRESS; 12C–12G COMPLETE**

Target release: Kuzco v1.5.0. Product and UX scope are frozen. No v1.5.0 tag
or release has been created or pushed. The existing annotated v1.0.0 tag remains
unchanged and resolves to release commit `948a600a860986a437a583dd4a70c55eeb7870be`.

## Entry inventory

The authoritative working tree is the repository root on branch `main`, beginning Phase 12 at commit
`9d6a765a6fcddb6fdb89e4864ea7442a7990bff6`. The remote is
`https://github.com/adiaz313/Kuzco.git`.

The entry audit found that substantial validated post-v1 implementation,
tests, documentation, and assets remain modified or untracked. The public
branch therefore does not yet equal the dogfooded product and is not a valid
publication candidate. README and project version metadata still describe
v1.0.0. Phase 12D–F must reconcile these only after 12A dogfood and the exact
RC soak gate.

Entry regression baseline: **376/376 passing**.

## 12A engineering validation

The complete entry suite passed. Bounded direct/provider checks then exercised
timekeeping, greeting, weather, read-only Calendar, Maps, travel time,
recommendations, and explicit unsupported behavior without recording private
answers. The active native host continued to own one listener process.

Four reproducible release defects were found:

1. A configured optional document that had been moved or deleted caused every
   foreground CLI request—including deterministic time—to abort during eager
   path validation. `configuration.documents()` now omits nonexistent optional
   configured paths. Explicit user-supplied `--docs` paths still fail fast.
   Document questions with no available collection follow the existing honest
   no-document behavior; unrelated capabilities remain available.
2. “Turn up the display brightness” missed the established deferred-brightness
   matcher and fell into unrelated document/model handling. The bounded parser
   now recognizes that natural ordering and returns the existing truthful
   unsupported response with zero Llama/native calls. Timer creation receives
   the same deterministic, honest deferred treatment.

3. The dogfood phrase “recommend lunch near my next appointment” did not match
   the existing calendar-relative recommendation grammar. It fell through to
   the general model path, took more than two minutes, and incorrectly attempted
   document retrieval. The bounded recommendation grammar now covers natural
   lunch/dinner/food/restaurant wording near the next appointment. The existing
   EventKit → MapKit implementation remains unchanged. Real-provider validation
   routed with zero Llama calls and selected the appointment venue itself as the
   grounded zero-distance food/nightlife candidate in 0.952 seconds; no private
   event or venue payload was retained in the report or logs.

4. “What do you remember about me?” treated `me` as a literal full-text search
   topic, so it could report no memories even while duplicate detection found
   an existing preference in the authoritative memory table. Explicit
   whole-profile recall for `me` or `myself` now returns the bounded, most-recent
   memory list directly from SQLite. Topic-specific recall remains unchanged,
   and an empty database returns a truthful empty-state response.

Focused regression coverage was added for all four defects. The new authoritative
engineering baseline is **382/382 passing**.

The active dogfooding memory database remains user data outside the repository.
No SQLite database is tracked or present in the publication tree; database and
sidecar patterns remain excluded by `.gitignore`, and a fresh installation still
starts without a memory database. The production fix was validated against the
active database without printing, copying, or modifying stored memory content.

The menu-bar model status was simplified from three states to a binary health
signal. A configured model that LM Studio can reach now reads **Available** in
green whether it is loaded or idle; an absent model, stopped server, or failed
status request reads **Unavailable** in red. Pausing Kuzco does not turn a
reachable model into a warning state.

No product capability, Skill, provider, dependency, or security authority was
added. Apple Podcasts, display brightness, timers, and Kuzco-owned local
notifications remain unsupported/deferred.

## 12A closure

Phase 12A is formally complete. Human dogfooding exercised conversation,
greetings, timekeeping, weather, web/current information, document retrieval,
explicit memory, reminders, bounded Mac controls, Apple Music, read-only
Calendar, Maps/Places, travel-time composition, recommendations, wake/STT/TTS,
the perimeter indicator, and menu lifecycle control. Cross-capability checks
included calendar-relative travel and recommendations, current-location-backed
weather and places, follow-ups, audio-device recovery, pause/resume, and honest
unsupported requests.

Native validation covered EventKit Calendar and Reminders, MapKit search and
routing, CoreAudio volume/mute, Apple Music playback, the signed menu host, the
Sherpa/Whisper/Piper voice path, and LM Studio availability. Reproduced defects
were corrected at their narrow responsible layers: missing optional document
configuration, unsupported brightness/timer routing, calendar-relative meal
recommendation grammar, whole-profile memory recall, and binary local-model
status presentation. Each received regression coverage; the complete validated
result is **382/382 passing**.

Known limitations remain intentionally unchanged: Llama-backed requests can be
slower than deterministic paths; provider-backed Maps, weather, and web behavior
depends on network/native services; route and place estimates are not
guarantees; and model-backed synthesis can still be imperfect. Apple Podcasts
control, display brightness, timers, Kuzco-owned notifications, arbitrary shell
execution, generic AppleScript/Shortcuts, and unrestricted computer control
remain unsupported or deferred and continue to fail honestly.

## 12B — exact executable release candidate

The frozen executable candidate is commit
`b8ca7134719d2cc81543855636f6731715541cb3` on `main`. Its tree was clean,
the full suite passed **382/382**, the tracked `uv.lock` was unchanged at RC
establishment, and the signed background host was rebuilt and installed from
that repository. The launch configuration points to the canonical repository
and the separate private data root. The required multi-day soak began on
2026-09-22 and remains in progress; no elapsed-time claim is made here.

## 12C — v1.5.0 identity and scope lock

Product and UX scope are frozen as Kuzco v1.5.0. The shipping architecture is
deterministic routing/Skills plus narrow policy-authorized tools and native
helpers, with the local Llama 3.1 8B used where language interpretation or
synthesis is useful. Sherpa, Whisper, and Piper remain local wake/STT/TTS.
Network-backed behavior is limited to structured weather, DDGS/public webpage
retrieval, and Apple MapKit/Places. EventKit Calendar is read-only; Reminders and
bounded Mac/Music actions remain explicit local actions.

Unsupported/deferred behavior remains Apple Podcasts control, display
brightness, timers, Kuzco-owned notifications, Calendar writes, arbitrary shell
or AppleScript/Shortcuts, browser automation, file deletion, keyboard/mouse
automation, and unrestricted computer control. Known limitations include manual
technical installation, slower/fallible Llama synthesis, provider/network
availability, route-estimate uncertainty, missing MapKit ratings, and native
Music/output-device constraints. The immutable v1.0.0 release still resolves to
`948a600a860986a437a583dd4a70c55eeb7870be`; no v1.5.0 tag exists.

## 12D — canonical repository synchronization

The canonical publication repository is this repository on `main`. Commit
`3c2f3170b31f9629f948a5ddbb58302a072a6151` is the documentation/version-only
descendant of executable RC `b8ca713…`; the diff contains README, release notes,
security/architecture/runtime documentation, and matching project/lock version
metadata only. No executable behavior differs from the soaked RC.

The public tree contains source, synthetic fixtures, tests, public configuration
defaults, two intentional menu artwork files, documentation, licenses, and
attribution. `kuzco-v1-data` remains outside it. Other local Kuzco directories
are historical rollback/private/training installations and are neither Git
inputs nor runtime dependencies. A public clone initializes its own data root
with `documents = []` and does not discover or import another installation.

## 12E — security and privacy audit

- **Secrets/history:** current-tree and reachable-history scans found no API
  keys, tokens, private keys, credentials, `.env` data, or developer secrets.
  Keychain remains runtime-only; no authenticated integration is exposed.
- **Personal data:** no personal documents, databases/WAL files, logs,
  transcripts, recordings, screenshots, private configuration, Calendar or
  Reminder contents, memory exports, search history, or recommendation history
  are tracked. User-derived memory/reminder/playlist test language was replaced
  with synthetic examples before the executable RC commit.
- **Sea Foods regression:** current-tree, reachable-history, filename, and
  content scans found no Sea Foods, seaweed-dog-food, derived chunk, embedding,
  or private RAG fixture material.
- **Location:** no real-user coordinate, route, search-center, Calendar
  destination, recommendation destination, or MapKit cache is present. Tests
  use visibly synthetic values; runtime logs retain only operation/outcome/count.
- **Paths and assets:** no public runtime/configuration instruction depends on
  `/Users/armando` or another developer path. Both intentional menu PNGs are
  tracked, self-contained, hash-stable, and contain no embedded personal text.
  Finder provenance extended attributes are local filesystem metadata and do
  not travel through Git.
- **Logging/data separation:** background logs redact transcripts/final answers;
  security logs accept bounded action/risk/decision/outcome metadata only.
  Calendar/Reminder/location payloads are not placed in ordinary logs or memory.
  `.gitignore` covers environments, caches, local configuration, databases,
  journals, logs/JSONL, audio, model weights, build output, and local state.
- **Policy:** tool execution still passes through the deterministic immutable
  registry and request-scope validation. Fixed native adapters pass user values
  as arguments/data; no generic shell, AppleScript, Shortcuts, deletion, or UI
  automation surface exists. Menu enable/disable controls lifecycle only.
- **Dependency/static checks:** exact `uv 0.12.11` resolved 68 packages and
  reported the installed 41-package runtime already synchronized. `pip-audit
  2.10.1` found no known vulnerabilities. Bandit 1.9.4 scanned 5,641 source
  lines with no medium/high findings (62 reviewed low-severity process-launch
  findings). Audit tools lived in an isolated `/tmp` environment, not runtime.

## 12F — publication documentation

The README was rewritten as v1.5.0 product documentation rather than a roadmap
appendix. It describes local versus network/native processing, deterministic and
Llama responsibilities, the verified capabilities and exclusions, permissions,
data layout, security boundary, manual installation, menu lifecycle, and current
green Available/red Unavailable model semantics. `docs/RUNTIME.md` retains the
exact model repository/file, hashes, context/runtime settings, loopback controls,
and the versioned `runtime/llama31.jinja` correction. The template hash remains
`99ad124d24124d52abe41296654fa0275e7ba840bf7272189a14135f019b37a9`.
Project metadata and lock metadata now agree on 1.5.0. Concise public release
notes are in `RELEASE_NOTES_v1.5.0.md`. Current-facing documentation contains no
obsolete orange or three-state model-status language; historical evaluation
reports retain accurate historical states.

## 12G — clean-install engineering proof

A fresh local clone at documentation commit `3c2f317…` used separate `/tmp`
Python, uv cache, virtual environment, and `KUZCO_HOME`. Following the README
downloaded Python 3.14.7 and installed all 41 locked runtime distributions,
initialized five generic configuration files, downloaded checksum-verified
runtime assets, built Whisper and all native helpers, and built/verified the
signed menu host with its repository-owned icon. The fresh configuration had
`documents = []`, no database, and no file under its empty logs directory.

The clean clone passed **382/382**. Doctor passed platform/Python,
configuration, asset/build hashes, Sherpa/Whisper initialization, the explicit
template hash, and live no-tools and structured local-Llama probes. Bounded
smoke checks passed deterministic time, Calculator, empty-memory behavior,
synthetic Northwind RAG, current public web retrieval, and local conversation.
Privacy-preserving native checks passed Calendar, Reminders, and MapKit while
recording only success/counts. After explicit operations, an empty memory DB and
bounded security metadata were created as designed; no prior user state was
imported.

Setup friction classified for the next distribution project: uv was not on the
development shell PATH and was bootstrapped at its documented pinned version;
asset installation downloads/compiles substantial components; LM Studio/model/
template setup and macOS permissions remain manual; Whisper emits upstream CMake
warnings; and current MapKit source emits macOS 26 deprecation warnings while
remaining functional. No installer, wizard, downloader shell, or packaging
architecture was added.

The clean service also passed its human lifecycle and voice check. The user
confirmed the menu showed Kuzco running with Wake Word On and Local Model
Available; wake, STT, the perimeter indicator, and Piper completed a time
request; disabling Kuzco showed Paused and Wake Word Off, prevented wake
activation, and correctly left Local Model green and Available; re-enabling
restored wake operation; a greeting completed through Piper; and Quit removed
the menu item. After this isolated check, the normal service using the private
Kuzco data directory was restored and verified running. No clean-install test
state replaced or entered the user's normal private data directory.
