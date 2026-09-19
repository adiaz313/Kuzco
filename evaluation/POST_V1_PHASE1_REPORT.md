# Post-v1 Phase 1 baseline

Phase 1 reconciled the public repository and active installation after the first
release. No post-v1 capability was introduced.

## Immutable release and canonical source

- The annotated `v1.0.0` tag remains at `948a600a860986a437a583dd4a70c55eeb7870be` locally and remotely.
- The canonical repository is this GitHub repository's `main` branch.
- The human's two public README commits were fast-forwarded into the local branch before any correction; no history or tag was rewritten.
- The active background service uses this repository as its source and retains the separate existing user-data directory. The previous source tree remains available for rollback.

## Demonstrated corrections

- The README now describes the released local-first assistant, provides the real clone URL, and removes current-state release-candidate instructions. Current architecture and runtime notes were brought into line with v1.0.0; historical evaluation reports retain their original wording.
- Package metadata and its lockfile now identify version `1.0.0`. Runtime dependencies and model configuration did not change.
- Background weather requests now ask macOS for location permission in the context that requested the forecast. The prior failure was `permission_required` even though a Terminal-launched helper could resolve location.
- An unambiguous upcoming game can be answered from a matching schedule page only when the season year, weekday, date, and kickoff agree. Otherwise the existing evidence-based model path remains. Exact schedule pages now outrank keyword-heavy roundups. This is generic schedule handling, without team-specific facts or rules.

## Audit and validation

- The published branch, release tag, README, setup/runtime documentation, license, attribution, examples, tests, and tracked artifacts were inspected. Documentation links resolve.
- Bounded privacy/secret recheck found no tracked personal documents, user databases, recordings, logs, virtual environments, developer-machine paths, private-derived fixture text, or credential-shaped values. The example document is synthetic.
- The locked project environment installed offline and passed **308/308** automated tests, including security regressions and native macOS checks. The lockfile check passed.
- Production Python/Swift source matched the dogfooded installation before the bounded weather and schedule fixes.
- Live local checks: deterministic time, synthetic document retrieval, and a public Lions schedule lookup worked. The schedule lookup answered in 1.6 seconds with no Llama call when the exact typed form and official schedule were available.
- Human voice check: greeting, time, Mac Utility, and synthetic memory requests passed. After the fixes, the human confirmed weather and Lions answers passed. The background log confirmed weather location success.
- The background log also recorded a **43.7-second** Llama call on the spoken Lions retest. Thus the generic direct schedule path is not guaranteed for every transcription/result set. This remains a known v1 latency limitation; no broader voice or web redesign was started.
- The MacBook microphone was the selected input during this validation. A device transition was not repeated in this phase; the existing audio-switching behavior and prior dogfooding evidence remain intact.

## Remaining known limitations

Llama-backed conversation can be slow; some definitions and web-evidence
syntheses can be imperfect; document-context processing can add delay. DDGS and
webpage extraction depend on external sites. Weather needs macOS location
permission and network access. These are recorded limitations, not new Phase 1
features. Phase 2 timers, reminders, and tasks have not begun.
