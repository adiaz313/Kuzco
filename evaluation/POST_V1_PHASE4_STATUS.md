# Phase 4 final validation status (2026-09-20)

`A` = automated regression; `N` = actual native macOS/application result; `V` = wake → Whisper → policy/tool → Piper result. A code path alone is not validation.

| Capability | Implemented? | Mechanism | A | N | V | Risk | Status / next action |
|---|---|---|---|---|---|---|---|
| Open app | Yes | Existing validated `/usr/bin/open -a` | Yes | Chrome opened | Chrome opened | LOCAL_ACTION | Preserve |
| Focus running app | Yes | Exact running-name AppKit helper | Yes | Running Music focused; missing app failed clearly | Yes, final human checklist | LOCAL_ACTION | Validated |
| Quit app | No | AppKit normal terminate candidate | No | No | No | Would be consequential LOCAL_ACTION | Deferred: no trusted voice confirmation for unsaved work; no force quit |
| Volume up/down | Yes | CoreAudio default output scalar, 10-point step + readback | Yes | Yes, user observed volume change | Yes, up/down and exact “turn up the volume” | LOCAL_ACTION | Validated |
| Set volume | Yes | CoreAudio bounded 0–100 + readback | Yes | Yes | Yes, 40% request | LOCAL_ACTION | Validated |
| Mute/unmute | Yes | CoreAudio mute property + readback | Yes | Yes | Yes, complete mute → unmute cycle | LOCAL_ACTION | Validated |
| Music play | Yes | Fixed compiled Music AppleScript + separate state verification | Yes | Started from stopped player | Yes, user confirmed audible playback | LOCAL_ACTION | Validated |
| Music pause/resume | Yes | Same fixed Music adapter | Yes | Paused/playing verified | Yes, final human checklist | LOCAL_ACTION | Validated |
| Music next/previous | Yes | Same fixed Music adapter | Yes | Track identity changed in multi-song queue; no-change failed | Yes, final human checklist | LOCAL_ACTION | Validated |
| Music named playlist/song | Yes | Exact unique native library match | Yes | Intended selection and playback verified; missing content failed | Yes; playlist passed focused repeat after intermittent failures | LOCAL_ACTION | Validated with intermittent voice name mismatch documented |
| Music named artist/album | No reliable playback queue | Music track metadata exists | Deferral tested | No | No | LOCAL_ACTION if later implemented | Deferred: one matching track does not establish artist/album playback |
| Podcasts transport/content | No | No bundled Podcasts scripting dictionary or demonstrated bounded third-party interface | Explicit unsupported route tested | No | No | Would be LOCAL_ACTION | Deferred pending a supported reliable interface; no GUI/Shortcuts workaround |
| Display brightness | No | No supported built-in display write path established | Explicit unsupported route tested | No | No | Would be LOCAL_ACTION | Deferred as brittle/disproportionate |

The existing security policy checks exact action and arguments against the current utterance. Music requires macOS Automation consent for Kuzco Background. No general AppleScript, shell, GUI, screen, keyboard, or mouse capability has been added.

Final full regression suite: **330/330 passing**. Podcasts, brightness, app
quit, and artist/album-wide Music queues retain their documented deferrals.
Phase 4 is complete; Phase 5 has not started.
