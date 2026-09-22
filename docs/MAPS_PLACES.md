# Maps / Places

Kuzco's post-v1 Maps/Places integration is a narrow signed Swift helper built
on Apple MapKit and Core Location. It does not scrape or automate the Maps UI.

Implemented primitives:

- structured address and point-of-interest search;
- explicit multiple-candidate results rather than silent selection;
- current-location-relative search when explicitly requested;
- current route distance and ETA for driving, walking, transit, and cycling
  when Apple supplies that mode in the requested area;
- opening an explicitly requested, resolved route in Apple Maps.

Search results may contain a provider identifier, name, formatted address,
coordinates, category, phone, and website when Apple supplies them. Missing
fields remain missing. Business hours are not reliably exposed by this MapKit
interface and are deferred. Recommendations, preference ranking, leave-time
reasoning, calendar-aware travel, navigation, and location history are outside
this integration.

Place search and directions contact Apple's MapKit service. The minimum query
leaving the Mac is the place text; nearby searches also use the current
location, while routing sends origin, destination, and transport mode. The
local Llama model, prompts, conversation history, documents, memory, and Kuzco
personality are not sent. Provider data is treated as untrusted information.

Current location is ephemeral. The **Kuzco Maps** helper may request macOS
Location Services permission on the first nearby or current-origin request.
Kuzco does not persist coordinates or place history, put precise coordinates
in ordinary logs, or expose location to unrelated requests. Denied permission,
offline service, no result, ambiguity, unsupported mode, and route failure are
distinct outcomes.

Examples:

```text
Where is Comerica Park?
Find coffee near me.
How far away is Comerica Park?
How long is the walking route from Campus Martius to Comerica Park?
Open driving directions to Comerica Park.
```

Opening a route is a narrowly registered local action. Trusted policy
re-parses the current utterance and requires exact destination and mode
arguments; provider text and model output cannot authorize another action.
