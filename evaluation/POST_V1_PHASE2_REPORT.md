# Post-v1 Phase 2 — Apple Reminders and lightweight tasks

Status: **Phase 2 complete; Apple Reminders/tasks validated for the intended use**. Timers are
intentionally deferred under the product owner's revised Phase 2 decision.

## Implementation

`reminder_intent.py` conservatively parses whole requests. Clear requests take a
direct path before model inference. Unsupported or ambiguous scheduled wording
asks for a time rather than guessing. Supported relative intervals, explicit
today/tomorrow/weekday AM/PM times, and documented “tonight” / “tomorrow morning”
defaults are converted in the local timezone. After voice testing, weekday
dayparts such as “on Monday morning” were added; Kuzco now confirms the concrete
date and 9 AM default rather than requiring an exact clock time.

`reminders.py` invokes a small signed Swift/EventKit helper. Apple Reminders is
the sole record of tasks/reminders, due times, completion, and alert delivery.
Unscheduled tasks are ordinary Reminders items without a due date. No Kuzco
scheduler, timer, or notification service was added. The helper needs macOS
**Full Access to Reminders**; denied/unavailable access is reported plainly.

The existing security policy classifies listing as `READ_ONLY` and creation,
completion, and removal as distinct `LOCAL_ACTION` operations. Every call must
match the current user's explicit request. Completion/removal first selects one
unique incomplete native item; ambiguity or missing identifiers fail closed.
No bulk action exists. Reminder contents are omitted from ordinary security logs
and unrelated conversation/model history. Requested lists are bounded.

## Validation to date

- Native Swift helper typechecked and built with the installed compatible macOS
  15.4 SDK. The current machine's default Command Line Tools SDK/compiler pair
  does not match; a matching SDK must be selected or the tools repaired for a
  fresh build on this Mac.
- Native EventKit read succeeded outside the automated-test sandbox; only the
  result count was inspected, not personal reminder contents.
- New focused tests: 10. Full suite: **318/318 passing** with a compatible
  `SDKROOT` and a writable Clang module cache.
- Active background Kuzco was restarted with this source; voice operation and
  native create/complete/remove still require human validation.

## Background permission correction

The first spoken “on Monday morning” request passed deterministic routing and
security policy but failed inside EventKit. macOS TCC attributed the child
Reminders helper's request to **Kuzco Background**, then explicitly refused it
because the responsible app lacked `NSRemindersUsageDescription`. Terminal-led
read/create/remove checks worked, which isolated the failure to the background
permission context. Both the background and helper bundles now declare the
legacy Reminders purpose key and the full-access key. The background app was
rebuilt and restarted. Human approval of the macOS prompt and a repeated voice
check remain pending. No reminder was created by the failed voice request.

The repeated spoken request passed after the rebuild. The local security log
records `reminders_create` success, the wake/STT/assistant/Piper cycle returned
to idle, and the user confirmed the new reminder appeared in Apple Reminders on
their iPhone. This validates the scheduled-create voice path and observed
cross-device behavior for this installation. Listing, completion, removal, and
ambiguous selection still await the remaining representative voice checks.

## List and completion follow-up

The next voice checks exposed two general usability failures. A list utterance
missed the conservative direct parser; model fallback took roughly 77 seconds,
attempted a policy-denied `reminders_list`, then searched local documents. A
synthetic item was created with the recognized title “phase 2 tests”; the next
completion request passed policy but failed to select the item, and a subsequent
unrecognized completion wording was denied by policy. The protected policy
boundary behaved correctly, but the user experience did not.

The direct parser now covers common list variants and routes unclear reminder
list wording to a short clarification instead of documents/LLM, provided the
utterance clearly concerns reminders and does not ask about documents, web, or
the meaning of the word. Item selection
normalizes spoken number words/digits and singular/plural forms, but still
requires exactly one matching native item. Vague “mark it complete” and similar
references now ask for the item's name without attempting a tool call. A bounded
diagnostic records only an action name and failure category, never reminder
content. The full suite is **322/322 passing**. Background Kuzco was restarted.
The user subsequently reported that all retested interactions worked. Security
logs independently confirm a complete wake/voice sequence with native create,
list, and complete outcomes marked successful, no denied policy actions, and
return to idle after speech. The logs omit transcript and reminder content, so
the precise cause of the earlier spoken wording failures is not established.
Removal and ambiguous-match behavior pass automated coverage; those particular
voice edge cases were not separately evidenced in the privacy-preserving logs.
The product owner accepted the tested functionality and explicitly chose to
advance without further Phase 2 voice checks. No additional capability was
added as part of this closure.

## Roadmap implications

Timers remain deferred because a supported native set/inspect/cancel Clock
interface was not established, and a Kuzco timer/scheduler was declined for this
cycle. Apple Reminders already owns persistence, scheduling, and native delivery.
The separately planned notification phase therefore lacks a demonstrated
immediate reminder dependency and should be reevaluated by the roadmap owner.
Phase 3 has **not** started.
