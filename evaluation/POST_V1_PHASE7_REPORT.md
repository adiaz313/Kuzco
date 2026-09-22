# Post-v1 Phase 7 — Greeting Composition

Status: **PHASE 7 COMPLETE — GREETING COMPOSITION VALIDATED**.
Phase 8 has not begun.

## Baseline

The Phase 6 RC and its **342/342** passing test baseline were preserved. The
existing deterministic Greeting Skill produced a response in approximately
**0.05 ms** on average, with zero Llama calls and no tools. That immediate
plain greeting remains the mandatory fallback.

## Composition architecture

Phase 7 remains deterministic:

`greeting → local daypart + bounded optional context → one short response`

Time supplies only morning, afternoon, or evening from the existing local
clock. Optional Weather and Calendar reads start in parallel and share a
**350 ms** deadline. Results are cached for five minutes after being reduced
to safe signals. A late, failed, denied, malformed, offline, or unavailable
source is omitted silently. There are **zero Llama calls**.

The selector adds zero or one observation. Weather is eligible only for a
high precipitation chance, snow, thunderstorms, or exceptional heat/cold.
Calendar is eligible only when the next timed event is within 90 minutes or
there are at least four timed events that day. Ordinary weather and an
unremarkable schedule produce a normal greeting. This is deliberately not a
daily or morning briefing system.

## Privacy and security

`greeting_calendar_context` is a new `READ_ONLY` policy action authorized only
for a current, complete greeting utterance. The EventKit adapter converts the
day's events to three structural fields: timed-event count, all-day count, and
the next timed start. Event titles, locations, calendar names, and full event
objects are discarded before the Greeting Skill receives the result.

Weather uses the existing validated `get_weather` integration. External data
remains untrusted numeric evidence. Neither raw Weather nor Calendar data is
sent to Llama, Memory, Reminders, or unrelated Skills. Ordinary security logs
contain action metadata but no context contents. Greeting adds no action or
write capability.

## Failure behavior and performance

The existing plain greeting is returned whenever optional context is absent
or misses the shared deadline. Optional source errors are not spoken during a
greeting. Focused tests verify the deadline returns promptly even while a
provider is slow.

Synthetic in-process measurements retain sub-millisecond composition once
signals are cached. The fresh optional-context path is capped at about **350
ms** before TTS. A foreground native attempt measured approximately **0.36
seconds** and correctly fell back, but macOS applied a different
permission/application identity than the installed background host. Final
real-provider timing and usefulness therefore require the background voice
check below.

## Automated validation

Eight focused Phase 7 tests cover dayparts, bounded personality, meaningful
Weather signals, structural Calendar signals, Weather priority, one-context
selection, provider failure, deadline fallback, zero Llama calls, history
privacy, policy enforcement, native adapter redaction, and deliberate context
omission. Existing Greeting, Weather, Phase 5 Calendar, Phase 6 Calendar Skill,
security, and full-product tests remain intact.

The complete suite passes **350/350** after Phase 7 implementation.

## Real-provider and human validation

The active background build successfully completed four representative spoken
greetings. The user confirmed that immediacy, natural wording, variation,
selective context behavior, privacy, speech, and visual return to idle all
worked.

Privacy-bounded runtime logs confirm four complete wake → Whisper → Greeting
Composition → Piper → idle cycles. The fresh context attempt returned the
greeting at the **350 ms** deadline; EventKit completed its structural read in
approximately **37 ms**, while Weather completed after the response and safely
populated the short-lived cache. The next three greetings composed in under a
millisecond before TTS. This demonstrates both grounded native access and the
required rule that slow optional Weather never delays greeting past budget.

Security records show both context operations authorized as `READ_ONLY` and
completed successfully. The records contain action metadata only; no event
title, location, forecast payload, transcript, or response content appears.
The final complete regression suite passes **350/350**.

## Known limitations and deferred ideas

The deterministic thresholds are intentionally conservative and may omit a
context a user would have enjoyed. Context is cached briefly, so an immediately
changed forecast or calendar may not appear until cache expiry. Phase 7 does
not use event contents, Memory, Reminders, news, email, proactive speech, or a
model-written greeting. Maps, Places, travel time, recommendations, and a
general composition framework remain deferred. Background Kuzco is running the
validated Phase 7 build. Phase 8 has not started.
