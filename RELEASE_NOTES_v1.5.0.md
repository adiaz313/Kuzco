# Kuzco v1.5.0

Kuzco v1.5.0 expands the local-first macOS assistant while retaining the v1
security boundary and deterministic-first architecture.

## Highlights

- Apple Reminders support for listing, creating, completing, and uniquely
  removing reminders and tasks.
- Bounded native Mac controls for application focus, output volume/mute, and
  selected Apple Music playback operations.
- Read-only Calendar integration and deterministic schedule answers.
- Contextual local greetings with bounded optional time, weather, and schedule
  signals.
- Apple MapKit place lookup, routes, travel-time calculations, and grounded
  nearby recommendations.
- A native signed menu-bar host with wake/runtime status, a real master switch,
  and clean quit behavior.
- Binary model health: **Available** in green when the configured LM Studio model
  is reachable, otherwise **Unavailable** in red.
- Reliability, privacy, policy, audio-device recovery, and regression coverage
  improvements across the voice and native-integration paths.

## Boundaries

The new integrations remain narrow and policy-controlled. v1.5.0 does not add
shell access, arbitrary AppleScript/Shortcuts, browser automation, Calendar
writes, unrestricted computer control, Apple Podcasts control, display
brightness, timers, or a Kuzco-owned notification subsystem.

See the README for installation, model/template configuration, permissions,
network use, privacy boundaries, and known limitations.
