# Post-v1 Phase 5 — read-only Calendar integration

Status: **PHASE 5 COMPLETE — READ-ONLY CALENDAR INTEGRATION VALIDATED**.
Phase 6 has not begun.

## Investigation and selected mechanism

Apple EventKit's `EKEventStore` has a native event-range predicate and event
query, including occurrences of recurring events. The installed Reminders
helper already demonstrates a signed, purpose-limited EventKit app bundle,
but Calendar needs its own consent and event-specific code. A separate tiny
Calendar helper avoids adding Calendar access to the existing Reminders
process. It will accept bounded date-range JSON and return only structured
event fields needed for the request. No writes, event editor, cache, calendar
database, or generalized scripting interface will be included.

macOS does not offer read-only EventKit authorization for events: reading
requires `requestFullAccessToEvents`, which grants OS-level read/write access.
The product's read-only boundary is therefore the trusted helper's *code*:
its input schema and dispatch expose queries only and it never calls EventKit
save/remove APIs. Calendar permission denial, restriction, timeout and native
failure must remain distinct from an authorized empty result.

Sources: [Apple EventKit access guidance](https://developer.apple.com/documentation/EventKit/accessing-the-event-store),
[full-access request](https://developer.apple.com/documentation/eventkit/ekeventstore/requestfullaccesstoevents%28completion%3A%29),
[event-range predicate](https://developer.apple.com/documentation/eventkit/ekeventstore/predicateforevents%28withstart%3Aend%3Acalendars%3A%29),
and [event retrieval](https://developer.apple.com/documentation/eventkit/retrieving-events-and-reminders).

The Python layer will compute local day/range boundaries and an upcoming-event
horizon; EventKit owns occurrence expansion and source Calendar state. Results
stay structured. Exact, full-request recognition for today, tomorrow and next
event/meeting is enough to expose the integration now; broader Calendar task
interpretation belongs to Phase 6. Calendar data is never generic personality
context, greeting context, SQLite memory, or ordinary log content.

## Validation

## Implemented boundary

`native/CalendarRead.swift` is a signed, separate **Kuzco Calendar** EventKit
helper. Its input allows only `day`, `next`, and an internal bounded `range`
query. It has no event-construction, save, remove, edit, RSVP, invitation, or
rescheduling code. `calendar_read.py` validates input and native output and
maps denied permission, permission timeout, invalid input, unavailable helper,
timeout, and malformed output separately. An authorized empty event list is
not treated as an access failure.

The user-exposed Phase 5 surface is deliberately small:

- “What's on my calendar today/tomorrow?” queries a local day boundary.
- “What's my next event?” returns the next event within 30 days.
- “What's my next meeting/appointment?” returns the next *timed Calendar
  event* within 30 days. EventKit does not establish that an event is truly a
  meeting, so the response says “timed calendar event.”

The integration also has a private, bounded 31-day range primitive needed to
prove overlap/empty-range behavior and support a later Phase 6 Skill. Broader
date/time language, free/busy interpretation, follow-ups, and compositional
schedule reasoning remain Phase 6 work.

`calendar_day` and `calendar_next` are `READ_ONLY` actions. Trusted policy
re-parses the current user utterance and requires exact action/arguments;
neither a model nor retrieved content can manufacture authorization. The
direct handler makes zero Llama calls. It retains only query kind and
success/error outcome in recent conversation history—not event titles,
times, calendars, or locations. Ordinary runtime/security logs contain only
bounded action metadata. Location is omitted by default and exists only as an
opt-in field on the internal range primitive.

Time semantics use the Mac's current Calendar/timezone. Day queries use local
midnight to the next local midnight, allowing Calendar to handle daylight
saving boundaries. EventKit expands matching recurring occurrences and
returns events overlapping the requested range. All-day events remain
explicit. “Next” excludes already-started occurrences; current in-progress
events still appear in a day query. A range with no overlapping event means
only that Calendar contains no conflict; Phase 5 does not infer personal
availability.

## Engineering validation

Six focused automated tests cover today/tomorrow boundaries, next event versus
next timed event, narrow routing and false positives, exact-request policy,
zero-model execution, exclusion of event content from history, empty and
multiple/all-day presentation, permission denial, malformed response,
timeout, invalid range, and the absence of native save/remove calls.

Real EventKit checks on this Mac returned:

- one actual all-day occurrence for today's day range;
- one actual all-day occurrence for tomorrow;
- the next timed event when all-day events were excluded;
- one event overlapping a bounded interval;
- zero events for a known empty future interval.

The native helper returned both authorized empty results and event results as
distinct structured data. No permission prompt appeared during this run;
EventKit reported existing usable access. Final human comparison with the
Calendar UI is still required before claiming the event data is correct from
the user's perspective.

Measured native retrieval after authorization was approximately **0.095 s**
for today, **0.066 s** for next timed event, and **0.089 s** for an empty
range. Two real requests through Kuzco's direct routing, policy, EventKit, and
response formatting completed in approximately **0.14 s** and **0.07 s**,
with zero Llama calls and before TTS.

The complete regression suite passes **336/336**. The normal isolated suite is
authoritative. A diagnostic run under the personal dogfooding `KUZCO_HOME`
made nine older CLI tests fail because that configuration references a now
missing personal DOCX; this is unrelated to Calendar and no personal
configuration was changed. Re-running in the normal isolated test setup
passed all 336 tests.

## Remaining gate and limitations

Human voice validation confirmed the representative today, tomorrow, next
event, and next timed-event requests against the user's actual Calendar through
wake → Whisper → deterministic Calendar routing → policy → EventKit → Piper.
The user reported that everything worked. Event locations are intentionally
not spoken by this minimal Phase 5 surface.
Calendar writes, free/busy language, arbitrary dates/ranges, follow-up
reasoning, greeting composition, and the Phase 6 Calendar Skill are excluded.

### First background validation correction

The first voice request reached deterministic Calendar routing and passed
Security/Policy, but EventKit failed before returning events. Inspection found
that the signed **Kuzco Calendar** helper declared its Calendar purpose while
the installed **Kuzco Background** parent app did not. macOS attributes the
background-launched privacy request to that parent process. The background
bundle now carries the same narrow `NSCalendarsFullAccessUsageDescription`;
the helper remains read-only in code. A regression test builds the service
bundle and verifies the declaration. The background app must be rebuilt and
the focused voice validation repeated; no routing or permission policy was
weakened.

After rebuilding/reinstalling the background bundle, macOS requested the
needed privacy permissions and the retry succeeded. Privacy-safe runtime and
security logs show successful `calendar_day` and `calendar_next` executions;
they contain no event titles or other Calendar content. The first permission
grant path took about 3.3 seconds at the native tool layer. Subsequent day and
next-event reads took about 0.03 seconds before TTS. Background Kuzco remains
running on the active Phase 5 source.

The final complete regression suite passes **337/337**. Phase 5 is closed.
Phase 6 has not started.
