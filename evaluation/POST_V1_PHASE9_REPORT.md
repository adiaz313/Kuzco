# Post-v1 Phase 9 — Travel Time Skill

Status: **PHASE 9 COMPLETE — TRAVEL TIME SKILL VALIDATED**.
Phase 10 has not begun.

## Architecture

Phase 9 adds one narrow deterministic Skill above the already validated Phase 8
MapKit integration, Phase 5/6 read-only Calendar stack, and Timekeeping code:

`explicit travel request → deterministic intent → policy → Calendar when needed
→ MapKit route → Python time arithmetic → concise grounded response`

The implementation adds no generalized composition framework, provider,
database, model, background-location behavior, or new dependency. Obvious
Travel Time requests make **zero Llama calls**. Existing Phase 8 place search,
distance, route, and Maps-open behavior remains intact.

## Implemented task classes

- current route duration to an explicit destination;
- distance through the existing Phase 8 route path;
- arrival feasibility against an explicit time;
- deterministic leave time against an explicit time;
- an explicit user-supplied buffer such as time to park;
- route duration or leave time for the next or one unambiguous named Calendar
  appointment when it has a usable location;
- immediate time-remaining follow-up after a grounded departure calculation.

Driving remains the default. Driving, walking, cycling, and transit are the only
supported modes. Unsupported modes fail explicitly.

## Fact and interpretation boundaries

**MAPKIT / ROUTING FACTS:** destination resolution, current distance, route
duration, mode, and estimate timestamp come from the Phase 8 provider boundary.

**DETERMINISTIC COMPUTATION:** Python computes target timestamps, departure
times, estimated arrival, remaining time, day rollover, and passed/started
states. A margin below ten minutes is deterministically described as “tight.”
Llama performs no arithmetic.

**USER-PROVIDED PREFERENCES / BUFFERS:** a buffer is included only when the user
explicitly supplies it. No parking time or safety margin is silently invented,
and no buffer preference is persisted.

**KUZCO INTERPRETATION:** deterministic presentation chooses concise language
and describes provider values as current estimates rather than guarantees. It
does not invent traffic, parking, destination, event, time, or certainty.

## Calendar composition and ambiguity

The Skill reuses EventKit through the existing read-only Calendar adapter. It
resolves the next timed event or one unambiguous named event, checks for a usable
location, then passes that location request-locally to MapKit. Multiple matching
events, a missing event, missing location, unavailable Calendar permission, an
unresolved destination, and an unavailable route remain distinct failures.
Calendar event titles and locations do not enter generic Llama context.

Destination resolution remains owned by Phase 8: one sufficiently grounded
candidate proceeds; ambiguity and no-result conditions are reported rather than
silently selected.

## Security and privacy

`travel_route` is a machine-classified `READ_ONLY` action. Trusted policy
re-parses the current utterance and requires exact destination, Calendar
selector, and mode arguments. Model output, Skill text, webpage/document
content, and provider data cannot authorize or alter the action. Malformed or
unclassified requests fail closed.

Current location remains ephemeral and permission-controlled. Event locations
are used only for the explicitly requested travel task. Neither is added to
Memory. Conversation history retains only bounded sanitized outcome/context;
ordinary operational logging records Skill selection, Calendar use, mode,
success/error, and timing without destination, coordinates, address, event
location, route payload, or transcript. There is no location or route history.

## Failure behavior

The implementation distinguishes current-location failure, destination
ambiguity/no result, Calendar ambiguity/missing event/missing location or
permission, route/network/provider failure, unsupported transport mode,
already-passed target, already-passed departure, already-started event, and
malformed structured data. Failures do not fall through to invented model
answers.

## Automated validation

Seven focused test groups cover grammar and false positives, supported and
unsupported modes, explicit deadlines and buffers, no implicit buffer,
departure/arrival arithmetic, deterministic tight/late decisions, passed and
started states, day-boundary behavior, malformed data, Calendar resolution and
failures, exact-request policy, zero-model execution, immediate follow-up, and
privacy-safe history/logging.

The complete suite passes **364/364**, up from the 357-test Phase 8 baseline.

## Native/provider validation

Real MapKit/EventKit checks on this Mac produced:

- Comerica Park travel duration: **0.633 seconds**, about 16 minutes driving;
- leave-time calculation for a stated deadline: **0.799 seconds**;
- feasibility with an explicit 15-minute parking buffer: **0.479 seconds**;
- next Calendar appointment query: **0.102 seconds**, correctly reporting that
  the naturally available event had no usable location.

Every path used zero Llama calls. Values are provider/network dependent and
exclude TTS. No fake Calendar event was created, and no precise location or
event payload was retained as evidence.

## Known limitations and deferred ideas

The Skill intentionally does not provide recommendations, personalized place
ranking, ratings, persistent travel modes/buffers, commute profiles, parking or
traffic prediction beyond MapKit, proactive leave notifications, location
history, geofencing, Calendar writes, or generalized conversational state.
Immediate sanitized follow-up context is bounded to the active session. Named
Calendar-event matching remains intentionally conservative. Provider-backed
routes require network and regional availability.

Human wake, speech, spoken-answer, and usefulness validation passed for explicit
destination travel duration, deterministic leave time, arrival feasibility with
an explicit parking buffer, immediate time-remaining follow-up, and
Calendar-aware travel to the user's next event. The user confirmed the final
Calendar-aware result provided a working grounded answer through the complete
wake → STT → Skill → EventKit → MapKit → deterministic computation → Piper
path.

The first human Calendar-aware travel check exposed an adapter mismatch: the
purpose-limited EventKit helper correctly requires `include_location=true`, but
the Travel Skill's range request initially omitted it. EventKit therefore
withheld the location even though the user's next event had one. The Skill now
requests locations only on this explicit travel path, validates the optional
field at the Python boundary, and passes it request-locally to MapKit. A
regression asserts both the flag and the exact handoff. No title or address was
written to diagnostic output or retained state.

After that correction, the focused Calendar/Travel suite and final complete
regression suite pass. Background Kuzco is running the human-validated Phase 9
build. Phase 10 has not begun.
