# Phase 4 mechanism matrix (pre-implementation)

This matrix records the macOS interfaces present on the tested Mac before adding controls. Product freeze for this phase: bounded Mac actions only; no general script, shell, keyboard, screen or GUI automation.

| Action | Mechanism | Permission | Reliability / consequence | Decision and reason |
|---|---|---|---|---|
| Open app | Existing `/usr/bin/open -a` with validated name and fixed argv | None normally | Existing tested launch; local action | Preserve |
| Focus running app | AppKit `NSWorkspace` + exact `NSRunningApplication.localizedName` and `activate` | None normally | Detect not-running/ambiguous app; local action | Implement |
| Quit app | AppKit `NSRunningApplication.terminate` | None normally | Unsaved work is consequential; current voice path has no trusted confirmation interaction | Defer until confirmation UX exists; never force quit |
| Volume up/down | CoreAudio default output device scalar volume | None normally | Device may not expose settable volume; local action | Implement with bounded increment and readback |
| Set volume percentage | CoreAudio scalar volume, clamped 0–100 | None normally | Device capability varies; local action | Implement where settable, fail clearly otherwise |
| Mute/unmute | CoreAudio default output device mute property | None normally | Device capability varies; local action | Implement where settable, fail clearly otherwise |
| Music play/pause/resume | Music's bundled `com.apple.Music.sdef` commands | macOS Automation consent | Bounded fixed scripting adapter; local action | Implement and verify actual player state |
| Music next/previous | Music's bundled scripting dictionary | macOS Automation consent | May have no active queue; local action | Implement with state checks |
| Music named playlist | Music scripting dictionary playlist objects | macOS Automation consent | Exact native library match, ambiguity possible | Implement with unique match only |
| Music named artist | Music scripting dictionary track `artist` property | macOS Automation consent | A matching track does not create a reliable artist-wide playback queue | Defer |
| Music named album | Music scripting dictionary track `album` property | macOS Automation consent | A matching track does not create a reliable album queue; names can be ambiguous | Defer |
| Music named song | Music scripting dictionary track `name` property | macOS Automation consent | Duplicate names possible | Implement with unique match only |
| Podcasts play/resume/pause | No bundled Podcasts `.sdef`; App Intents metadata exists but no documented direct third-party invocation path identified | Would need other automation mechanism | Generic Shortcuts or UI automation would violate this phase boundary | Defer unless a supported bounded interface is found |
| Podcasts named show/latest episode | Same Podcasts interface limitation | Same | No reliable native library query and verified playback interface | Defer; no RSS/feed subsystem |
| Display brightness | No supported public per-display write API established for built-in Apple Silicon display | Would need private API or UI automation | Brittle, disproportionate to value | Defer |

Apple documents `NSRunningApplication` activation and normal termination, and CoreAudio's set-property interface. Music's scripting commands and playlist/track metadata are present in the installed app's own scripting dictionary. Podcasts has no comparable bundled dictionary on this Mac. All script source, if used, will be fixed and owned by Kuzco; user content will be passed as data arguments rather than interpolated into executable source.
