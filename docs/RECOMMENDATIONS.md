# Local place recommendations

Kuzco's Recommendations Skill helps choose among real local places
returned by Apple MapKit. It is deliberately bounded to local coffee, food,
category, distance-sensitive, and next-appointment-relative requests.

The flow is candidate-first: an explicit request selects a MapKit query and
search center, MapKit returns structured candidates, and deterministic Python
deduplicates and sorts at most five candidates by provider distance. Kuzco
speaks one closest grounded match and no more than two nearby alternatives.
The common path makes zero Llama calls.

MapKit does not provide reliable ratings, reviews, menus, prices, or current
hours through this interface. Kuzco does not invent those fields or describe a
place as best, popular, highly rated, open, inexpensive, or guaranteed to carry
a menu item. A specialized search such as “salad” is described as a MapKit
search match rather than verified menu evidence.

Current location is ephemeral and requested only for the active nearby search.
For “near my next appointment,” EventKit supplies the next event's location
only for that request; the title is not needed or spoken. Coordinates,
addresses, candidate sets, Calendar locations, recommendation history, and
inferred preferences are not added to Memory or ordinary conversation history.

This Skill does not book, order, call, message, purchase, or create Calendar or
Memory records. Ordinary Phase 8 place lookup and route actions remain separate.
