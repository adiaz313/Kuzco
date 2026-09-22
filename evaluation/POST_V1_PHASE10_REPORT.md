# Post-v1 Phase 10 — Recommendations Skill

Status: **PHASE 10 COMPLETE — RECOMMENDATIONS SKILL VALIDATED**.
Phase 11 has not begun.

## Architecture

Phase 10 adds one narrow local-place Skill:

`explicit recommendation request → trusted policy → current location or an
explicitly relevant next-event location → Apple MapKit candidates → deterministic
deduplication/distance ordering → concise grounded answer`

This is not a general recommendation engine. It adds no provider, database,
model, generalized composition framework, transaction, or persistent behavioral
profile. Ordinary Phase 8 search remains separate.

## Candidate-first grounding

**LLAMA INTERPRETS GROUNDED OPTIONS. IT DOES NOT INVENT THE WORLD AROUND THE
USER.** The initial bounded implementation goes further: its supported common
tasks need no Llama interpretation at all. MapKit owns candidate identity,
category, city, coordinates, and distance. Python owns deduplication, numeric
sorting, bounds, and presentation. Llama calls: **zero**.

The normalized provider set remains capped at eight. The Skill deduplicates it,
sorts structured distance numerically, retains at most five for consideration,
and speaks one primary closest match plus at most two alternatives. It does not
manufacture a quality score or break evidence-equivalent ties using invented
facts.

## Constraints and provider limitations

Supported grammar covers nearby coffee, lunch/dinner/food, a bounded explicit
category or search term such as salad, “close,” and food near the next Calendar
appointment. Explicit terms become MapKit natural-language queries. A search
match is not presented as verified menu evidence.

The current MapKit surface does not provide trustworthy ratings, review counts,
prices, menu contents, operating hours/status, availability, parking, wait
times, reservations, or popularity. Requests that require those fields fail
with a concise limitation before provider access. No additional provider was
added and none of these facts is inferred.

## Memory, Calendar, time, distance, and travel roles

Memory participation is intentionally absent from the initial implementation.
The existing explicit Memory store can hold preferences, but no broad/private
Memory search was justified merely to choose by grounded distance; no preference
is fabricated or automatically learned. A future bounded use requires evidence
that it materially improves selection without exposing unrelated memories.

Calendar participates only when the request explicitly says “near my next
appointment.” EventKit supplies the next timed event's location using the
purpose-limited location flag established in Phase 9. The title is unnecessary.
Missing Calendar access/event/location fails honestly without silently changing
the search center. Current time only defines “next”; no hours claim is made.

Distance from the chosen ephemeral center is the deterministic ranking signal.
Phase 9 route estimation is not run for each candidate, avoiding N-candidate
route latency. Travel-time-constrained recommendations and follow-up route
actions are deferred rather than generalized.

## Security and privacy

`recommend_places` is `READ_ONLY`. Trusted policy re-parses the current user
utterance and requires the exact query and Calendar selector. Llama, Skills,
MapKit fields, pages, documents, and Memory cannot authorize or mutate it.
Provider data crosses the strict Phase 8 normalization boundary and is treated
as untrusted data.

Current location and Calendar location are used only for the active request.
The implementation persists no coordinates, address, event title/location,
candidate set, search/recommendation history, selection, visit assumption, or
inferred preference. Conversation history retains only interaction outcome and
the final spoken answer. Ordinary logs retain Calendar-use flag, outcome,
candidate count, and timing without query or private payload.

## Failure behavior

No candidates, missing provider distance, location denial/failure, provider
failure/timeout, unresolved Calendar search center, missing Calendar event or
location, and unavailable Calendar remain distinct. Unsupported ratings,
prices, reviews, and hours do not start a search. The Skill never falls back to
model world knowledge.

## Automated validation

Seven focused test groups cover bounded routing and search/recommendation
separation, explicit constraints, deterministic distance ordering, candidate
deduplication/bounds, candidate-only output, absence of invented ratings/hours/
prices/menu claims, unsupported metadata, Calendar-purpose limitation,
Calendar/provider failures, exact-request security, zero-model execution,
privacy-safe history, and missing-distance behavior. Existing Maps, Travel,
Calendar, Memory, Greeting, Security, and voice behavior remains covered.

The complete suite passes **372/372**, up from the 364-test Phase 9 baseline.

## Native/provider validation and performance

The signed MapKit helper now supports one bounded `search_around` operation:
resolve the explicitly supplied Calendar location, search within its region,
and calculate candidate distances from that center. A real next-appointment
search completed in **1.487 seconds**, returned grounded food candidates, and
used zero Llama calls.

After rebuilding the ad-hoc signed helper, three engineering current-location
probes reached the native fixed **15-second** location timeout. This is a
permission/callback deployment state requiring the normal human permission and
background voice check; it is not being hidden as model latency or repaired by
speculative recommendation logic. Human validation must re-establish the
existing Phase 8 current-location permission and verify the common paths. The
subsequent background voice validation did so successfully.

## Known limitations and deferred ideas

MapKit relevance and provider availability determine candidate usefulness.
Ratings and business-detail fields remain unavailable. The Skill does not use
Memory, Llama, route-per-candidate computation, follow-up candidate state,
recommendation history, booking, ordering, calls, messages, purchases, or
proactive behavior. These omissions preserve evidence quality, privacy, speed,
and the roadmap boundary.

Engineering-controlled logic, native validation, and human voice/current-
location validation are complete. Feature development is frozen after this
successful Phase 10 closure; Phase 11 has not begun.

Initial human dogfooding exposed a provider-ordering defect: Python sorted only
the first eight MapKit relevance-ranked results, so closer candidates omitted
from that prefix could never win. The native adapter now retains up to 32
provider candidates internally, applies a tighter 15 km local search bias,
sorts by grounded distance at the location boundary, and only then emits the
existing eight-result maximum. Calendar-relative food searches also include the
resolved event place itself as a zero-distance candidate only when MapKit
classifies it as a grounded food/nightlife category. This does not infer menu,
rating, hours, or quality.

The next human pass found that coffee still preferred a distant result even
though the numeric ordering was correct. A bounded provider comparison showed
that MapKit natural-language searches for `coffee`, `coffee shop`, and `cafe`
all omitted known closer places. For generic coffee and restaurant intents, the
native adapter now uses MapKit's structured `MKLocalPointsOfInterestRequest`
with `.cafe` or `.restaurant`; constrained terms such as `salad` continue to use
natural-language search. Nearest-first distance ordering remains unchanged.

## Human validation and closure

Human voice validation passed for nearby coffee, close lunch, a constrained
salad search, and food near the next appointment. The first pass exposed poor
provider candidate coverage and failure to include an event venue that was
itself a restaurant/bar. Nearest-first collection and grounded center-place
handling corrected the appointment and lunch behavior. A second coffee check
exposed MapKit natural-language search's omission of closer cafés; the bounded
structured café-category request corrected it. The user confirmed the final
coffee request works.

The complete wake → STT → Recommendations Skill → current-location/EventKit as
needed → MapKit → deterministic selection → Piper path is validated. All
spoken candidates come from the request's normalized MapKit result set. No
ratings, hours, menu facts, prices, recommendation history, precise location,
or inferred preferences are created or persisted.

Phase 10 closes the current roadmap's feature-development scope. Feature
development stops here. Phase 11 release engineering has not begun.

Real-provider revalidation then selected the user's appointment venue itself at
**0.0 miles** and offered only grounded nearby alternatives in **1.156 seconds**
with zero Llama calls. Current-location probes after the second helper rebuild
again required macOS to re-establish the helper's location permission before
the final human voice retest.
