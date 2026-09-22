# Post-v1 Phase 4 — bounded Mac control

Status: **PHASE 4 COMPLETE — BOUNDED MAC + NATIVE MEDIA CONTROL VALIDATED**. Phase 5 has not begun.

## Mechanisms and scope

The [pre-implementation matrix](POST_V1_PHASE4_MATRIX.md) records every candidate. Existing app open remains unchanged. Focus uses a fixed AppKit helper and an exact running application name. Volume uses public CoreAudio default-output volume and mute properties with 0–100% bounds, 10-point relative steps, and readback. A device that lacks writable controls fails clearly. Music uses the installed app's own `com.apple.Music.sdef` through one fixed compiled AppleScript; the operation and content name are process arguments, never executable script source. It supports transport, exact playlist, and exact song in the native library. No catalog search, persistent library copy, or extra player was built.

App quit is deferred because unsaved work warrants trusted confirmation and the current voice flow lacks a reusable confirmation exchange. Artist/album-wide playback is deferred because selecting one matching track does not establish the requested queue. The tested Podcasts app has App Intents metadata but no bundled scripting dictionary or demonstrated supported third-party direct invocation path. Generic Shortcuts and GUI automation would break this phase's boundary; Podcasts is deferred. Brightness is also deferred for lack of a reliable supported write interface on this Mac. None of these deferred operations may be reported as completed.

Evidence: Apple's [NSRunningApplication](https://developer.apple.com/documentation/appkit/nsrunningapplication) exposes activation and normal termination; [CoreAudio](https://developer.apple.com/documentation/coreaudio/audioobjectsetpropertydata%28_%3A_%3A_%3A_%3A_%3A_%3A%29) exposes bounded property writes; Apple's [scripting guide](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/AboutScriptingTerminology.html) identifies the app-bundled `.sdef` dictionary as the supported command inventory. The local Music app contains playback commands and playlist/track metadata in that dictionary. This Mac's Podcasts app does not contain a comparable `.sdef`.

## Routing, policy, and privacy

`mac_intent.py` parses only complete explicit commands. `skills/mac_control.py` handles them before Llama. Every tool has action-level `LOCAL_ACTION` metadata and a deterministic policy check against the current utterance and exact arguments; the model, retrieved content, and Skill text cannot authorize a different action. The fixed adapters accept data only. No general AppleScript, shell, keyboard, mouse, screen, app-list, or window-control tool exists. Music library query details and application use are not persisted in Kuzco memory or ordinary logs. Automation consent is requested by macOS when Music control is first attempted.

## Validation so far

- Phase 2 baseline before edits: **322/322** tests passing.
- Native focus and CoreAudio helpers compile with the installed macOS 26.5 SDK. Music's fixed adapter compiles outside the command sandbox where its dictionary can be read. A missing-app focus probe returned `not_running` without changing the foreground app.
- Eight focused test cases cover routing, representative actions, boundaries,
  failure mapping, action-specific policy, and fixed script execution. The final
  full suite is **330/330 passing**. The background service was reinstalled with
  the Automation purpose text and is running from the active source tree.
- Measured deterministic intent parse: **0.0031 ms/request** over 10,000 local iterations. Missing-app focus returned in **278 ms**. A real volume adjustment completed in about **34 ms** of tool time in the background log; a stopped-player Music start completed in about **0.37 s** in a direct CLI check. No model call is required for these matched direct requests.

## Known limits / next gate

Music playback is limited to items present in the user's native library. A bare “play NAME” asks the user to specify playlist or song; it does not infer artist, album, or podcast category. Music must be granted Automation permission if macOS prompts. Output devices may not expose writable system volume. The implemented controls have passed representative wake → Whisper → policy → native app → Piper validation as detailed below.

## First live feedback and focused correction

The user reported volume down, explicit volume, mute, and Chrome launch working.
Unmute and “play music” failed, so further Music commands were not attempted.
The security log showed successful CoreAudio actions; unmute missed deterministic
wording, then the LLM's attempted `volume_mute` call was correctly denied by
policy. Its exact STT wording was not retained. Common explicit variants such as
“un mute”, “unmute it”, and “take it off mute” now remain in the direct path.

“Play music” reached the direct Music tool and failed. macOS Automation access
for Kuzco Background was on. Music's visible native player was stopped with its
Play, Previous, and Next controls disabled: there was no current selection to
resume. The fixed Music adapter now starts Music's native library playlist when
the player is stopped, then verifies a playing state. No separate media library
or player was added. A bounded failure-category log records no media names or
transcripts. The correction compiles, **329/329 tests pass**, and the background
service has been restarted. Focused human retest still failed for both commands.
The text request `Unmute` executes the direct CoreAudio path and verified mute=false
outside the command sandbox, so the spoken failure is before the native adapter:
Whisper's exact transcription was not retained by the privacy-preserving
background log, and the resulting phrase fell through to Llama and was denied
by deterministic policy. Further routing edits require the actual transcription.
`Play music` reached the direct Music action, but Music returned
`playback_failed`. The native library contains 107 tracks. The user confirmed
that the Music app can play a specifically selected song, while its empty
player Play button does nothing. Investigation found two adapter errors:
casting Music's player-state enum `as text` produced an opaque AppleEvent
constant instead of `stopped`, so the stopped-player library branch never ran;
and checking playback within the same AppleScript invocation returned stale
state before Music finished processing Play. The fixed script now compares
the enum directly and returns from the command; Python verifies state in a
separate bounded read. A stopped-player end-to-end `Play music` request
returned `player_state=playing` in 0.37 seconds without an LLM call.
The user confirmed Music playback through wake/Whisper/Piper. A one-time
foreground push-to-talk diagnostic then showed the exact Whisper output for
the spoken unmute request: `unmute, unmute, unmute.` The whole-utterance parser
treated that repetition as a different request and fell through to Llama.
The parser now accepts up to four identical `unmute` or `mute` repetitions,
while mixed or explanatory utterances remain unmatched. The captured phrase
uses the direct tool with zero model calls in regression tests. **330/330**
tests pass, and background Kuzco has been restored on the MacBook microphone.
During a real mute → unmute foreground cycle, Whisper captured `Cuzco. Cuzco.
Mute.` for mute and `Cuz go, unmute.` for unmute. Mute used the direct path;
`Cuz go` was not recognized as a wake-name spelling, so unmute fell through
to Llama and was denied. The Mac's sound was restored with the verified direct
text path. Wake-name cleanup and the Mac intent parser now accept only this
observed leading `cuz go` variant; no policy was weakened. A regression test
covers wake cleanup → direct routing → enforced CoreAudio action with zero
model calls. **330/330** tests pass. The user also reported one missed wake
attempt; no wake-detector tuning is part of this routing fix. Final spoken
mute/unmute revalidation passed in the active background service: the user
confirmed that sound muted and returned, and the local security log recorded
`volume_mute` EXECUTE/success for both requests. Music playback also passed
the user's background voice retest. Explicitly deferred controls remain
deferred.

## Volume phrasing follow-up

The user's exact failing phrase was “turn up the volume”; setting volume to
40% worked. The former fell through to Llama because the narrow parser only
accepted “turn the volume up,” and the security layer correctly denied the
model's proposed Mac action. The parser now accepts both word orders and a
small number of equivalent whole-request volume phrases. Explanations and
negated requests still do not authorize volume changes. The focused tests and
full **330/330** suite pass. Background Kuzco was restarted; the user confirmed
that the exact spoken phrase promptly raised the Mac's volume. The local
security log recorded `volume_adjust` EXECUTE/success for that request.

## Continuation: native validation and completion boundary

The [status matrix](POST_V1_PHASE4_STATUS.md) records the implementation,
automated, native, and voice evidence separately. Engineering-controlled
native checks from the active RC found:

| Request | Native result |
|---|---|
| Switch to Music | AppKit reported `focused=true` for the running app |
| Pause / resume | Music reported `paused` / `playing` after the commands |
| Play named playlist | Exact existing playlist selected and playing |
| Play named song | Exact library song selected and playing |
| Missing song / playlist | `not_found`, with no substitute content claimed |
| Next from multi-song playlist | Track identity changed |
| Next from one-song queue | Track identity unchanged; explicit failure returned |
| Previous from multi-song playlist | Track identity changed using Music's documented `back track` command |

The native checks exposed a false positive: earlier next/previous responses
only checked whether Music remained in the `playing` state. The fixed adapter
now checks track identity. Named playback checks that Music selected the
requested playlist or song in addition to being in `playing` state. Music's
`back track` restarts a song if it is well underway; Kuzco checks the track
identity and issues at most one more bounded back-track command to reach the
prior song. If identity never changes, it reports failure. No additional
player, library copy, generic script tool, or permission was added.

Each implemented new action remains `LOCAL_ACTION` with exact-request
authorization. Music requires macOS Automation consent; focus and CoreAudio
normally need no new privacy permission. Native library titles are used only
for exact selection and verification, never stored in ordinary logs or memory.
The direct paths do not call Llama. Representative measured processing was
~34 ms for a volume change, ~0.37 s for a stopped-player Music start, and
~0.72 s for app focus in the native CLI probe; native Music library lookups
can take a few seconds. The final complete suite passes **330/330**.

Apple Podcasts remains deferred: this Mac's Podcasts app has no scripting
dictionary, and no supported bounded third-party control/selection interface
was demonstrated. Apple's [Podcasts playback guide](https://support.apple.com/guide/podcasts/play-podcasts-pod970198c2/mac)
documents UI/Siri use, while Apple's [scripting guide](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/AboutScriptingTerminology.html)
identifies the app dictionary as the supported scripting surface. Generic
Shortcuts, simulated keys, and GUI automation are outside this phase's
boundary. Artist/album-wide Music queues, app quit, and brightness remain
deferred for the reasons above. Phase 5 has not started.

The final human checklist covered focus of a running app; Music pause, resume,
next, previous, named playlist, named song, and missing-content failure. The
user reported that all except the initial playlist request worked. Earlier
human checks had already confirmed app open, volume up/down/set, mute/unmute,
and Music play. The playlist's subsequent foreground wake → Whisper → direct
Skill → security → Music → Piper test passed, with native playback verified.

## Playlist voice follow-up

The user reported that the playlist request failed while the other final voice
checks worked. The first attempt fell through to the general model, whose
`music_play_named` proposal was denied by the exact-request security policy.
A second attempt reached the authorized direct Music tool but returned
`not_found`. Ordinary background logs omit transcripts and media names, so
they cannot establish which name Whisper supplied on either failed attempt.
A controlled foreground wake test then transcribed the expected wake name and
named-playlist request; wake cleanup produced the intended request, the direct Skill
selected `music_play_named` with no model call, Music verified playback, and
the user confirmed it worked. Background Kuzco was restored afterward.
These results show an intermittent voice/transcription or phrasing mismatch,
not a reproducible native playlist-control failure. No matching or security
rule has been loosened without the actual failed transcription. This remains
a documented reliability limitation; another failed attempt should be captured
in foreground debug mode before changing matching behavior.

## Podcasts and brightness disposition

The current source has no Apple Podcasts action, adapter, tool registration,
or native execution path. The earlier mechanism investigation found no
Podcasts scripting dictionary on this Mac and no demonstrated supported,
bounded third-party invocation for its App Intents. Therefore **Podcasts is
DEFERRED**, including transport, named shows, and latest episodes. Four-layer
success validation against the native app is inapplicable: there is no
implemented action to validate or claim as successful. A focused regression
run passed 8/8. Additional representative direct-path probes for resume,
pause, named show, and latest episode returned the explicit unsupported
message with zero model calls and zero tool calls. A nonexistent show cannot
be classified as not found by Kuzco because it cannot query Podcasts content;
it correctly receives the same unsupported response. Closed-app, no-current-
playback, permission, ambiguity, and native-failure cases likewise have no
implemented adapter and are not claimed as tested. No human voice test is
needed to establish native playback of an unimplemented capability.

The existing Phase 4 mechanism matrix already investigated display brightness
for the built-in Apple Silicon display: no suitable supported public write
interface was established, while private APIs or UI automation would be
brittle for a low-priority control. **Brightness is DEFERRED**. A direct-path
probe of a brightness request returned the explicit unsupported message with
zero model calls and zero tool calls. Neither decision changes working Mac
control or Music. Phase 5 has not begun.

## Final roadmap reconciliation and regression

Every implemented capability in the Phase 4 mechanism matrix has automated
coverage, a real native/system check, and representative end-to-end human
voice confirmation. Existing application open remained intact. The final
human checklist's only reported failure was the playlist request, which was
then successfully repeated through the complete voice path; its earlier
intermittent failures remain documented above. The report's earlier
"remaining human voice check" was historical and is superseded by these
results. Deferred controls (quit, artist/album queues, Podcasts, brightness)
do not have an implementation to validate and were not represented as
successful native actions. Exact-request Security/Policy remains in force;
failed or ambiguous Music requests do not claim playback. No generic
script, shell, keyboard, screen, or GUI control was introduced.

The final full regression suite passed **330/330** tests. There were no
production-code changes during the final reconciliation. Phase 4 is closed
with the intermittent playlist transcription/name-resolution behavior as a
known limitation. **Phase 5 has not started.**
