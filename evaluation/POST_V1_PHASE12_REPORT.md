# Post-v1 Phase 12 — v1.5.0 Release Engineering

Status: **12A COMPLETE — v1.5.0 RC FORMATION IN PROGRESS**

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

## Gates not yet passed

The integrated human dogfood pass exercised the requested core, information,
native-assistant, composition, menu-control, and honest unsupported paths. The
user reported that every requested item worked except the calendar-relative
lunch wording described above; after its bounded correction and background
restart, the user confirmed that retest works. Phase 12A therefore passes.

Phase 12B's exact-RC multi-day soak has not begun. Version lock, repository synchronization,
security/privacy/history audits, public documentation rewrite, clean install,
publication approval, publication, and post-publication verification remain
pending in their prescribed order.
