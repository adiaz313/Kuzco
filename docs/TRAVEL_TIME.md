# Travel Time

Kuzco's post-v1 Travel Time Skill composes the existing read-only Calendar,
MapKit/Places, current-location, and Timekeeping components. It supports bounded
questions about current route duration and distance, reaching an explicit
destination by a stated time, when to leave, and the next or a named Calendar
appointment when that event has a usable location.

Route durations and distances come from Apple MapKit. Event times and locations
come from EventKit. Current time and every arrival/departure calculation are
handled by deterministic Python code; Llama does not calculate or supply these
facts. Driving is the default. Driving, walking, cycling, and transit are the
supported modes, subject to regional MapKit availability.

Kuzco applies an extra buffer only when the user states one. Travel and arrival
times are presented as current estimates rather than guarantees. Ambiguous or
missing destinations, Calendar events without locations, unavailable
permissions, unsupported modes, and unavailable routes fail explicitly instead
of being guessed.

Current location and Calendar event location are used only for the active
request. Kuzco does not create travel history or persist coordinates, addresses,
route payloads, or Calendar locations in Memory or ordinary logs. MapKit sends
the minimum route/place inputs needed to Apple's service; local orchestration,
documents, Memory, personality, and general conversation history remain local.

