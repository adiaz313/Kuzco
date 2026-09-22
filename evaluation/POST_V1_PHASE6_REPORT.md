# Post-v1 Phase 6 — Calendar Skill

Status: **PHASE 6 COMPLETE — CALENDAR SKILL VALIDATED**.
Phase 7 has not begun.

## Proposed architecture

The validated Phase 5 EventKit helper remains the sole Calendar integration.
Phase 6 adds one narrow deterministic Skill above it:

`explicit schedule task → bounded range/next query → structured events → Python time computation → concise response`

Existing Phase 5 requests keep their current handlers and latency. The new
Skill will recognize only complete schedule-oriented requests for day or
afternoon overview, time until the next timed event, first/last timed event,
and back-to-back timed events. These tasks have reliable structured solutions,
so the first implementation needs no Llama call. This avoids putting personal
Calendar data into model prompts while still proving the Skill composition
pattern.

The Skill will reuse the Mac's local calendar/timezone and EventKit's overlap
query. Afternoon means 12:00–17:00 local; “after lunch” means 13:00 through
local day end. A “meeting” remains a timed Calendar event, not a semantic
classification. Back-to-back means consecutive timed events with a gap from
zero through five minutes; overlaps are conflicts rather than back-to-back.
No-event language describes Calendar evidence, not personal availability.

The range action will be `READ_ONLY`, authorized by re-parsing the current
utterance and matching the exact computed interval. The assistant will retain
only task/outcome metadata in conversation history and ordinary logs. Calendar
records remain request-local. No write path, greeting composition, proactive
announcement, follow-up framework, web search, or new model is included.

## Validation

## Implemented task classes

The Skill now supports bounded whole-request variants for:

- today/tomorrow schedule overview;
- today's afternoon (12:00–17:00) and after-lunch (13:00–day end) periods;
- deterministic time until the next event or timed event;
- first/last timed event today or tomorrow;
- back-to-back timed events today, defined as a gap of zero through five
  minutes. Overlaps are not mislabeled as back-to-back.

All Phase 6 paths are deterministic and make **zero Llama calls**. This is a
deliberate outcome, not an omission: EventKit retrieval plus Python date/time
computation answers the implemented tasks reliably. Existing Phase 5 today,
tomorrow, next event, and next timed-event handlers retain their original
`CALENDAR_READ` path.

`calendar_range` is a new `READ_ONLY` action. Security re-parses the current
utterance and requires exact start, end, and event-kind arguments. The range
is capped at 31 days in Python and native code. EventKit returns structured
overlapping occurrences; `kind=timed` excludes all-day events at the native
boundary. Only task name and success/error outcome enter session history.
Calendar records do not enter memory, generic prompts, greetings, or ordinary
logs. There are still no Calendar write APIs.

“Meeting” and “appointment” remain intentionally described as timed Calendar
events because Calendar metadata does not prove semantic type. Empty periods
are described as Calendar having no events rather than asserting personal
availability. Event currently underway is reported as in progress. Long waits
are rendered in days/hours rather than a large number of hours.

## Validation completed so far

Five Phase 6 automated tests plus the seven Phase 5 Calendar tests cover:
task routing and false positives, local today/tomorrow/afternoon boundaries,
time-until arithmetic, in-progress events, first/last selection, all-day and
multiple events, empty periods, overlap versus back-to-back behavior,
permission/native errors, exact-request policy, zero-model execution, privacy
of history, and preservation of Phase 5 routing. Synthetic fixtures cover
back-to-back and overlap cases not present in the real Calendar.

Real EventKit validation on the active Calendar produced grounded answers for
today's all-day schedule, today's afternoon, time until the next timed event,
an empty first-timed-event day, and no back-to-back timed events. The initial
real run exposed overly verbose hour-only duration and generic empty-task
language; both were corrected in deterministic presentation logic and added
to regression coverage. Revalidation returned concise correct forms.

Measured end-to-end pre-TTS Skill execution against real EventKit was roughly
**0.06–0.12 seconds**, including retrieval, deterministic computation, policy,
and response formatting. Llama calls: **0**. Phase 5 direct paths remain
separate and unchanged.

The final complete automated suite passes **342/342**. Engineering-controlled
native validation passes.

Human validation also passes. The user successfully completed all four
representative voice requests against the active background assistant:

- “What does my day look like?”
- “What's my afternoon like?”
- “How much time before my next meeting?”
- “Do I have back-to-back meetings?”

Privacy-bounded runtime logs confirm four complete wake → Whisper → Calendar
Skill → EventKit → grounded response → Piper → idle cycles. Security records
show `calendar_range` authorized and completed as `READ_ONLY` for each request.
Native Calendar retrieval took approximately **0.028–0.036 seconds** per
request, with **zero Llama calls**. Event titles and other Calendar contents
were not written to ordinary runtime or security logs.

The active background assistant is running the Phase 6 implementation. Phase
7 has not started.
