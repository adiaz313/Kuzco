# Post-v1 Phase 11 — Menu Bar Status and Master Control

Status: **PHASE 11 COMPLETE — VALIDATED**

Entry baseline: 372/372 tests passing. Engineering baseline: 376/376
tests passing on September 21, 2026.

## Runtime investigation and architecture

The installed per-user LaunchAgent (`local.kuzco.background`) runs the signed
`Kuzco Background.app`. Before Phase 11 that native AppKit host already owned
exactly one `background.py` child. The Python child owns the listener lock,
Sherpa wake input, Whisper, agent, Piper, and visual state renderer. Its active
capture loop opens the selected microphone; unwinding that loop releases it.
The host already forwarded macOS wake notifications to the child with SIGUSR1.

Phase 11 extends that existing LSUIElement host. It does not add a daemon,
assistant, wake listener, audio path, or lifecycle manager. The menu starts and
stops the host's exact child. The existing listener lock remains a second line
of duplicate protection.

The chosen implementation is native AppKit in Swift because AppKit was already
part of Kuzco's built and signed background host and adds no dependency. A
Python menu package such as rumps/PyObjC would add a dependency and a competing
process lifecycle. A separate menu application would require cross-process
ownership and synchronization. Both were rejected as unnecessary.

## Artwork

The authoritative source remains unchanged:

- `assets/kuzco-menu-icon-source.png`
- 1278 × 1230 RGBA PNG
- SHA-256 `05a3986b3d5f829f58eaa6d9536eba8a33f284d1bdb975972c7bab3cd17c2be0`

The derived status asset is:

- `assets/kuzco-menu-icon-statusbar.png`
- 44 × 44 RGBA PNG
- SHA-256 `d603ff4de5b2dbfe87a3dca28d3e19a1576fa603c89e9adc67d663227f0f3181`

It crops the central llama/sunglasses badge and scales it for menu-bar use. An
initial human check found too much internal padding, so the derivative was
recropped from the authoritative source at 600 × 600 before scaling. The emblem
now occupies substantially more of the 44 × 44 canvas. A second human check
showed it still appeared small and high. The visible alpha bounds were measured,
shifted from center `(22.0, 18.5)` to the exact canvas center `(22.0, 21.5)`,
and its native menu display size was increased from 20 to 26 points. The source was neither
overwritten nor transformed in place. Final optical-size and appearance
validation remains required.

## State and control behavior

- **Kuzco Running** means the host's one Python child is alive.
- **Kuzco Paused** means the persisted master switch is off.
- **Kuzco Not Running** means enabled was requested but no child is alive.
- **Wake Word On** requires a private 0600 runtime record whose PID matches the
  host's exact child and whose listener flag is true. Enabled alone is not
  treated as listener readiness.
- **Local Model Running** means LM Studio's local `/api/v1/models` inventory
  reports the configured model with a loaded instance.
- **Local Model Available** means the configured model is present but unloaded.
- **Local Model Unavailable** covers an absent model, stopped server, malformed
  response, or inability to determine state.

The model check runs on menu open and every 15 seconds, has a two-second
timeout, and performs no inference.

The first human check also found that disabled informational menu items looked
dim and their plain dots conveyed no meaning. The corrected menu uses native
custom informational rows with dynamic `labelColor` text. Status dots use
dynamic system green for active/healthy, orange for model available but
unloaded, red for a real unavailable/not-running problem, and secondary label
color for intentional pause/off. These views remain informational rather than
pretending to be clickable commands.

Turning the master switch off persists `off` in the private data directory,
removes the readiness record, and terminates the exact assistant child. The
menu host stays alive. Turning it on starts one fresh child; a running-child
guard prevents duplicates. Unexpected child failure exits the host so the
existing launchd KeepAlive policy can perform its established bounded restart.

The initial checkmark menu item was replaced by a genuine native `NSSwitch`.
It invokes the same master action and state; no second toggle or lifecycle path
was introduced.

`Quit Kuzco` stops the child and unloads the LaunchAgent from the current GUI
session. This prevents KeepAlive from immediately respawning the menu or wake
listener. The installed plist remains available for `service.py start` and the
next normal login.

Startup behavior is conservative: the menu appears first, then the microphone
authorization result permits the child to start. It never reports listener On
before the child writes real readiness. On macOS wake, SIGUSR1 is forwarded
only while enabled and running. A disabled Kuzco therefore stays disabled.

## Security and privacy

Menu toggling and quitting are direct deterministic user controls. Neither
uses Llama, a Skill, nor the tool policy path, and neither grants any new
assistant action. Existing action-level authorization remains unchanged.

The runtime record contains only the assistant PID, a wake-listening boolean,
and an update timestamp, with owner-only permissions. The menu and bounded
logs contain no transcripts, prompts, memory, documents, calendar/reminder
data, location, credentials, or tool history.

## Performance

On the target Mac, the active native menu host sampled at 0.0% CPU and about
52 MB resident memory. The existing Python wake process was separate and
unchanged. With LM Studio unavailable during the sample, a local status probe
failed truthfully in approximately 0.01 seconds. Polling is limited to one
15-second local inventory request and menu-open refresh; there are zero Llama
calls and zero external provider calls.

## Validation

Automated coverage verifies the private content-free readiness record and
permissions, source/derived asset separation, service bundle resource and
model configuration, native lifecycle/status implementation, duplicate-child
guard, termination/bootout paths, and absence of chat-completion use in the
menu host. The complete suite passes: **376/376**.

The rebuilt signed application is installed and active. Native process
inspection found exactly one menu host (PID 11952) and one owned Python child
(PID 11963). The child's 0600 readiness record was present, and background logs
confirmed the selected MacBook microphone reached active wake listening.
LM Studio was not running during this inspection, so `Local Model Unavailable`
is the expected truthful state until it is restored.

Initial human validation confirmed that the menu and its control were functional, while finding
four presentation defects: undersized emblem, dim status text, nonsemantic
dots, and an insufficiently obvious checkmark control. Those findings produced
only the bounded icon and native-view corrections described above. After the
native row/switch refinement, a final asset pass placed the measured visible
emblem on the exact canvas center and increased its display size by 30%. The
user confirmed the resulting real menu-bar appearance “looks great.” The UI
changes retained the same previously validated lifecycle action, and the final
active-runtime check again found one host and one owned listener. Human visual
and functional validation therefore passes.

## Known limitations and deferred UI

This is operational status, not generalized diagnostics. It intentionally
does not explain why LM Studio is unavailable, expose audio-device controls,
show activity/history, or administer models. Status can lag by at most the
15-second polling interval unless the menu is opened. All dashboards,
preferences, update, installer, and manager concepts remain deferred and out
of scope.
