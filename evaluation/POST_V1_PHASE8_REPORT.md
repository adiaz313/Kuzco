# Post-v1 Phase 8 — Maps / Places Integration

Status: **PHASE 8 COMPLETE — MAPS / PLACES INTEGRATION VALIDATED**.
Phase 9 has not begun.

## Baseline and decision

Phase 8 began from the validated Phase 7 RC with **350/350** tests passing.
The installed macOS SDK, Apple documentation, and live probes established that
one signed Swift helper using MapKit and Core Location supplies the smallest
reliable architecture. No Python mapping library, paid API, browser, scraping,
GUI automation, AppleScript, database, or new model was added.

`explicit request → deterministic intent → policy → signed helper → Apple
MapKit/Core Location → validated structure → concise deterministic response`

Apple documents `MKLocalSearch` for addresses and points of interest,
`MKDirections` for Apple-server route and ETA data, and `MKMapItem` for opening
supported destinations/routes in Maps. The local SDK also exposes stable map
item identifiers on macOS 15+, point-of-interest categories, phone, website,
coordinates, and formatted addresses when available. Core Location uses a
separate purpose-described **Kuzco Maps** app identity.

## Investigation disposition

| Capability | Decision | Evidence / boundary |
|---|---|---|
| Place and address search | IMPLEMENT | `MKLocalSearch`; live unique and multi-result probes passed. |
| Name resolution | IMPLEMENT | Unique exact match or sole result only. Multiple plausible candidates remain explicit. |
| Current-location-relative search | IMPLEMENT | Ephemeral Core Location fix used only for an explicit “near me” request. Human permission validation remains. |
| Coordinates and straight-line location data | IMPLEMENT internally | Returned as grounded candidate fields, never spoken/persisted by default. |
| Distance and ETA | IMPLEMENT | `MKDirections.calculateETA`; current estimate, not guarantee. |
| Driving, walking, cycling, transit | IMPLEMENT | All four returned real estimates for a Detroit test route. Availability remains region dependent. |
| Open validated route in Apple Maps | IMPLEMENT | `MKMapItem.openMaps`; explicit exact request and trusted policy only. No GUI automation. |
| Phone, website, category, provider ID | IMPLEMENT when supplied | Optional `MKMapItem` fields; missing remains missing. |
| Dedicated details request | DEFER | Search already returns all reliable MapKit metadata required by this phase. |
| Business hours | DEFER | Not reliably exposed by this MapKit interface. |
| Full turn-by-turn route steps/navigation | REJECT for Phase 8 | Apple Maps owns navigation UI; Kuzco does not become a navigation engine. |
| External mapping provider | REJECT for current scope | Native MapKit met the bounded requirements without key, paid API, or another provider. |
| Recommendations and preference ranking | DEFER | Phase 10 work, not an integration primitive. |
| Leave-time/calendar reasoning | DEFER | Phase 9 work. |

The compatibility implementation reads `MKMapItem.placemark`, which remains
available on the project's macOS 14+ floor but is deprecated in the macOS 26
SDK in favor of newer address/location properties. This is a known maintenance
point, not a runtime defect; the live macOS 26 probe passed.

## Supported primitives

- `places_search(query, near)` — structured address/POI candidates, up to eight.
- `route_estimate(origin, destination, mode)` — grounded current distance and
  ETA for a supported mode.
- `maps_open_route(destination, mode)` — opens only a resolved destination and
  explicit route in Apple Maps.

The user-facing grammar is deliberately bounded to place lookup, nearby search,
direct route distance/ETA, and explicit open-directions requests. It does not
interpret recommendations or “when should I leave?” questions.

Dogfooding found that reading full street addresses and ZIP codes aloud was
unnecessarily verbose. Human-facing place answers now prefer the provider's
city field, while the full address remains internal evidence for resolution
and Maps. Ambiguity responses no longer recite address lists. Nearby results
retain distance from the ephemeral location fix for a future grounded Skill.

## Ambiguity and failures

Resolution selects a result only when there is one exact-name match or one
total result. Otherwise the integration returns up to five structured
candidates and asks the user to be more specific. No result, ambiguity,
permission denial, location failure, timeout, provider/network failure,
unresolved origin/destination, unavailable route, unsupported mode, malformed
response, and Maps-open failure remain distinct outcomes.

Provider strings are untrusted data. Python enforces an allowlist of fields,
types, sizes, coordinate ranges, finite route numbers, timestamps, result
counts, and known errors. Unknown fields—including instruction-like content—
reject the response. Provider content never authorizes tools.

## Location, network, and privacy

Current location is requested only for a current-origin route or explicit
nearby search. The helper asks for When-in-Use permission, obtains one fix, and
stops location updates. It creates no location history and writes no location
state. Precise coordinates, route payloads, candidates, and provider IDs are
excluded from conversation tool history, Memory, and ordinary logs.

MapKit search and directions are Apple network services. Depending on the
operation, the place query, origin, destination, transport mode, and current
location leave the Mac for Apple. Kuzco does not send its system prompt,
personality, documents, memory, general conversation history, or Llama output.
The local model and orchestration remain local. Offline provider-backed search
and routing fail cleanly; Kuzco does not invent or substitute stale place data.

Ordinary logs retain only operation, outcome, timing, and candidate count.
Foreground `--debug` may show the explicitly requested arguments and bounded
result summary for developer inspection, but not the full provider payload.

## Security

Place search and route estimates are `READ_ONLY`. Opening a route is a narrow
`LOCAL_ACTION`, comparable to opening a requested app: it changes local UI but
does not book, purchase, message, post, or modify remote state. Policy re-parses
the current utterance and requires the exact destination and transport mode.
Missing request scope, changed arguments, compound/negated wording, malformed
provider data, or model/provider text cannot authorize execution.

## Performance and real-provider evidence

Live Apple MapKit results on this Mac:

- Comerica Park unique lookup: about **0.38–0.65 seconds**, one correct result.
- Starbucks Detroit: about **0.65 seconds**, four candidates retained as
  ambiguity rather than silently selected.
- Detroit to Ann Arbor driving ETA: about **1.0 second**, approximately 42.9
  miles and 47 minutes at the sampled time.
- Campus Martius Park to Comerica Park: driving **0.74 s**, walking **0.58 s**,
  cycling **0.55 s**, and transit **0.66 s** provider latency.
- Complete Kuzco text path: unique place **0.52 s**, ambiguity **0.36 s**, route
  **0.98 s**; **zero Llama calls**.

These values are network/provider dependent and are current estimates rather
than guarantees.

## Automated validation

Seven focused tests cover bounded routing, false positives, risk metadata,
exact current-request authorization, malformed and injection-like provider
data, multiline Apple addresses, finite/ranged coordinates, distinct empty /
ambiguous / failure output, route formatting, explicit open-route output,
zero-model direct execution, private history, timeout, missing helper, and
malformed native responses. Existing Greeting, Calendar, Weather, security,
voice, and product tests remain intact.

The complete suite passes **357/357**.

Human dogfooding later exposed one nearby-coffee phrasing that missed the
deterministic grammar and incurred roughly **61 seconds** in the general Llama
path. The native search itself had taken about **3.8 seconds** in the preceding
run. Bounded variants such as “find me a place to get coffee near me” and
“where can I get coffee near me?” now route directly to MapKit, with regression
coverage. This fixes the wrong-layer delay without implementing Phase 10
ranking.

## Human validation

Human voice validation passed for unique place lookup, current-location nearby
search, ambiguous business search, current-origin distance/ETA, and opening a
resolved route in Apple Maps. The user confirmed speech and the complete
interaction behavior worked. A follow-up check confirmed the city-level answer
and concise ambiguity presentation.

Privacy-bounded logs confirm successful `READ_ONLY` place/route actions and a
successful `LOCAL_ACTION` route open, followed by normal return to idle. Logs
contain operation, timing, outcome, and candidate count without queries,
addresses, coordinates, destinations, or route payloads. The microphone also
recovered from a stale AirPods input to the MacBook microphone through the
already-validated audio recovery path.

After the natural coffee-phrase routing correction, a live current-location
MapKit run completed in about **5.0 seconds** with **zero Llama calls**. This is
substantially below the erroneous 61-second general-model fallback but remains
provider/location latency to revisit with the future recommendation experience.
The final complete suite passes **357/357**.

## Known limitations

MapKit requires network for useful place and route data and can throttle or
fail. Transit/cycling availability varies by region. Name-only queries can be
ambiguous. Business hours are deferred. The integration does not remember
places, recommend destinations, interpret calendar travel, calculate when to
leave, or navigate. Phase 9 has not started.

Dogfooding also established a concrete Phase 10 requirement: for a request
such as “find coffee near me,” the assistant should choose a useful candidate
instead of reading a list when reliable ranking evidence permits it. MapKit's
supported `MKMapItem` surface provides distance but not ratings on this Mac.
Phase 8 therefore preserves distance and explicit ambiguity without inventing
ratings; provider evaluation and assistant-style ranking remain Phase 10 work.

Background Kuzco is running the validated Phase 8 build. Phase 9 has not begun.
