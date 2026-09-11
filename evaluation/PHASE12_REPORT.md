# Phase 12 — release-candidate construction

**PHASE 12 COMPLETE — KUZCO v1 RELEASE CANDIDATE READY FOR PHASE 13**

Implementation, clean-install, security and bounded candidate background-startup
checks passed. Phase 13 has not begun. Nothing is published or tagged as v1.

Working Phase 11 source, configuration and environment inventory were preserved
privately before construction. Candidate source is separate. All original 245
tests and both personality files are retained unchanged. No personal state,
historical evaluation recordings, environments or model weights were copied.

The release candidate uses uv 0.12.11, Python 3.14.7, pinned runtime dependencies
and a committed lockfile. Native asset URLs, hashes and the Whisper source commit
are in assets.json. Configuration, assets, memory and logs use a separate data
root. No automatic personal-data migration occurs.

See docs/RUNTIME.md for the exact four-line historical template correction and
the explicit saved-template requirement. The model weights and working saved
template were not changed. Per-request SDK control was evaluated but the current
server did not accept its WebSocket connection, so it was not adopted.

## Candidate and clean installation

The source repository is `kuzco-release-candidate`, version `1.0.0rc1`.
`kuzco-clean-install` is a separate local Git clone used for clean installation.
No previous Git repository/history existed in the development source; only new
local construction history exists. There is no public remote or release tag.

The clean clone used an **empty uv cache**, a **newly downloaded managed Python
3.14.7**, locked wheels, and a fresh data root. It independently downloaded all
five manifest assets and built Whisper and the indicator. No development virtual
environment, model directories, database or private documents were copied.

All **257/257 tests passed** both in the construction environment and in the clean
managed-Python clone. The original 245 tests are byte-identical; 12 release tests
cover data separation, configuration, security enforcement, asset integrity,
archive safety, HTTPS/downgrade rejection and template behavior.

The lock resolves 68 packages across groups: 39 runtime distributions, two
release-test dependencies, and isolated security tooling. Baseline runtime versions
were retained; a proposed regex update was pinned back to the working version.
Rejected OpenWakeWord training dependencies are excluded from normal installation.
The optional adapter and its existing tests remain; Sherpa stays the default.

Actual host: Apple Silicon macOS **26.6.2**. macOS 14 is the dependency-wheel
minimum, not a separately tested OS. This was a fresh Python/cache/data install
on the same Mac, **not a second Mac or new macOS account**. Apple Command Line
Tools and the explicitly configured LM Studio application/server/model remained
shared system prerequisites. Native builds are reproducible from pinned sources,
not claimed byte-identical across different compilers/OS versions.

## Explicit data/configuration and security

`KUZCO_HOME` selects configuration, assets, SQLite memory and bounded logs outside
source. Defaults are inspectable repository files; initialized user overrides
are private files and are not overwritten on repeated setup. Fresh memory and
document lists are empty. `KUZCO_MEMORY_DB` remains an explicit legacy override;
unset it for a fresh installation. No automatic personal-data migration occurs.

TOML exposes loopback port, model identifier, background personality and document
paths. The existing voice/TTS/wake/security JSON settings remain separate. The
background launcher records the clone/data paths; background RAG receives the
configured document list. Skills and DDGS remain their existing implementations;
the policy disable list controls tool availability. Moving a clone requires
reinstalling its launcher. The per-user service label and listener lock remain
single-instance; installing another clone replaces that user's service.

Phase 11 policy, risk classifications, confirmation rules and untrusted-content
boundaries are preserved. New release testing checks a valid trusted Calculator
request is denied when disabled and allowed when re-enabled. Original model,
Skill, web, RAG, memory, credential and logging security tests all remain green.

The clean managed-Python installation passed a native Keychain synthetic test:
missing → store → retrieve → redacted representation → delete → missing. No real
credential was read/copied. `KUZCO_HOME` does not create a separate Keychain
identity; the OS account namespace remains shared and is documented.

Audit: **41 installed distributions checked, zero reported vulnerabilities**
(includes the two release-test dependencies). Bandit: **30 LOW, zero MEDIUM,
zero HIGH** after explicit HTTPS/downgrade protection was added to the installer.
No bulk upgrades or analysis suppressions. These audits do not cover all native,
model or macOS components or prove absence of every vulnerability.

## LM Studio/Bionic resolution

The embedded GGUF template and saved override differ by exactly four added lines
normalizing empty/missing tool lists to `none`. Nonempty tools still render.
The installed GGUF exactly matches upstream LFS SHA-256
`f2be3e1a239c12c9f3f01a962b11fb2807f8032fdb63b0a5502ea42ddef55e44` at repository
revision `8601e6db71269a2b12255ebdf09ab75becf22cc8`. Model weights are unmodified.

The candidate explicitly sends `tool_choice: "none"` and retains its application
JSON decision protocol. That parameter alone is **not** claimed to replace the
template fix. The official SDK's per-request-template path failed its bounded
local WebSocket connection probe; no SDK/transport migration was adopted.

The accepted fallback is a **versioned, documented corrected-template requirement**,
with exact comparison against exported/saved active configuration and live
no-tools/structured-output checks. Both live checks passed in both environments.
The existing saved override remains unchanged. **Stock-template independence is
not claimed.** Its dependency is now explicit; the working bridge was not removed.
See docs/RUNTIME.md for the exact change, setup and hashes.

## Bounded smoke results

These validate installation, not Phase 13 answer quality or everyday usability.

| Check | Result | Observed wall time |
|---|---|---:|
| Time/direct Python | Correct clock-only response with “sir” | 0.030 s |
| Calculator | Launch accepted and acknowledged | 0.099 s |
| Empty memory | Accurately reported no matching stored memory | 0.008 s |
| Fictional product note | Correct idea, fictional caveat retained | 37.627 s |
| Governor web question | Search/answer completed with source links | 67.224 s |
| Short conversational acknowledgment | Human-facing answer returned | 59.107 s |
| Fresh Piper rendering | Nonempty local speech audio | 2.974 s |
| Fresh Whisper transcription | Synthetic “What time is it?” transcribed exactly | 1.556 s |

Doctor passed platform, configuration, asset hashes, native builds, Sherpa/Whisper
setup, exact template, plain local response and structured local response in the
clean clone. Only 8B was loaded afterward; 1B/3B remain installed but unloaded.
Observed runtime allocations remain 51,200 context / four slots, with a one-hour
idle TTL. The existing auto-loader's smaller requested context can be overridden
by saved settings. These are explicit Phase 13 measurement inputs, not silently
changed defaults. Slow language/retrieval results were recorded, not optimized.

Two synthetic Piper “Kuzco” fixtures did not activate Sherpa. A same-PCM comparison
also failed on the unchanged working baseline; no candidate-specific regression
was demonstrated, and wake tuning was not reopened. Synthetic results are not
human microphone validation. Separate native STT/TTS and existing voice/state/
loop automated tests passed.

## Background startup validation

The fresh candidate background app built and launched, then macOS requested its
own microphone permission. Python voice startup correctly waited for approval.
The permission-only launcher subsequently confirmed permission, and the bounded
startup check was repeated successfully.

The clean managed-Python candidate started, entered IDLE, selected **MacBook Air
Microphone**, and logged **“Microphone initialized; wake listening active”** at
23:53:16 local time on September 9, 2026. The test then stopped the candidate and
restored the original launch configuration and working Kuzco. Personal state and
the original app remain intact. The candidate is not silently replacing the
user's normal background assistant.

New installations must grant permission for their own built **Kuzco Background**
app. `service.py permissions` opens its permission-only launcher without a second
listener. This was a startup/microphone-open validation, not a new human spoken
accuracy trial. Full repeated spoken interaction belongs to Phase 13; it is not
claimed from startup logs or synthetic audio.

## License/hygiene review and next phase

The candidate is source-only GPL-3.0-only; third-party terms remain separate.
Llama template license/notice and Piper's model card are retained. Installed
distribution license metadata is recorded in dependency-licenses.json. No model
weights or binaries are bundled. Sherpa's selected weight archive lacks a clear
model license; upstream clarification remains unresolved. Do not mirror/bundle
those weights or claim commercial redistribution rights. Direct upstream download
does not establish redistribution rights. Complete that review before publishing
model bundles; Piper voice attribution/share-alike terms also remain applicable.

Tracked-file inspection found no developer absolute paths, private-key blocks or
service-token patterns. File inventory excluded personal/state/model artifacts.
This is bounded inspection, not a universal secret-detection guarantee. Private
historical reports, audio, full development backups and environments are excluded.

Phase 13 retains greeting/definition quality, retrieval delays, Lions/web reliability,
follow-ups, everyday voice use and failure recovery. It must test this actual
managed installation, template and data layout. No new Skills, integrations,
models or speech engines were introduced; no dogfooding or publication occurred.

**PHASE 12 COMPLETE — KUZCO v1 RELEASE CANDIDATE READY FOR PHASE 13.** Stop here;
the next phase requires the user's instruction. Public release/model-bundling
decisions remain separate from this source candidate's completion.


## Final fresh-install promotion validation — 2026-09-10

The fresh installation from RC commit `ebb2062f2852a64b25832bf3d500c99aef7358a9` is now the active login/background Kuzco. This supersedes the earlier restoration of the historical development service. The old installation and rollback snapshots remain preserved.

The documented clone, locked uv installation, configuration initialization, upstream asset installation and service installation paths were used with separate Python, virtual environment, cache and data directories. No historical virtual environment, personal memory database, private documents or configuration was copied. Document configuration is empty; RAG validation used only the supplied fictional fixture. Synthetic memory was removed after testing. No credentials were imported; Keychain remains the same OS-account facility, not a newly isolated account. Existing macOS build tools, runtime application and the verified public GGUF are explicit shared prerequisites, not a claim of a new OS installation or freshly downloaded Llama weights.

Full fresh-install regression: **257/257 passed** (8.230 seconds). Native Sherpa initialization, Piper synthesis/playback and Whisper transcription passed. Time, Calculator, memory lifecycle, fictional RAG and public web retrieval passed bounded smoke checks. Unknown shell actions remained denied; the unchanged security regression suite passed. The combined smoke's final conversation timed out at 120 seconds; a fresh-session repeat returned an acknowledgment in 3.895 seconds. This remains documented latency evidence for Phase 13, not a silently discarded failure.

The user confirmed both complete wake interactions: time and Calculator, with speech and return to IDLE. Runtime logs confirm both lifecycles and repeated listening on MacBook Air Microphone. The spoken time request used two Llama calls (43.503 and 9.382 seconds), whereas Calculator used the direct tool path. Investigate that time-routing/latency behavior in Phase 13; no tuning was performed here. AirPods/iPhone device handoff disrupted audio selection during setup and is also a Phase 13 follow-up. Built-in microphone/speakers subsequently passed.

Only Llama 3.1 8B is loaded, at the documented 51,200 context and four parallel slots. 1B/3B remain unloaded. The historical saved template was reset before explicitly applying the candidate-owned corrected template; its active contents match `runtime/llama31.jinja` exactly. This is **not an unmodified stock template**: the historical behavior is now an explicit reproducible installation requirement, with no hidden dependency claimed. Runtime logging is configured with verbose request logging off and content redaction on.

**The Kuzco currently running on this Mac was installed from the reproducible v1 release-candidate process and is materially representative of what another user will receive.** Application code is unchanged from the validated commit; this final record is documentation only. No public tag/release was created. Phase 13 has not begun.

**PHASE 12 COMPLETE — KUZCO v1 RELEASE CANDIDATE READY FOR PHASE 13.**
