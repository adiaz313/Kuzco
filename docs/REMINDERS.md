# Apple Reminders and lightweight tasks

Kuzco uses the supported macOS EventKit framework. Apple Reminders owns storage,
alerts, completion, and any synchronization configured by the user. A task is an
Apple Reminder without a due time. No Kuzco reminder database or scheduler exists.

The normal asset setup builds the small signed **Kuzco Reminders** helper from
`native/Reminders.swift` into the installation's private `assets` directory. The
first reminder request asks for **Full Access to Reminders** in macOS Privacy &
Security. EventKit offers this scope for reading and updating reminders. If denied,
Kuzco reports the failure; it does not bypass the permission or claim success.
In wake mode, macOS may show the permission under **Kuzco Background** because
that app is responsible for launching the helper. Allow that app if prompted.
Run `python reminders.py` from the installed project if the helper needs rebuilding.

Supported direct requests include “Add oil change to my reminders,” “What reminders
do I have?”, “Mark oil change complete,” “Remove my oil change reminder,” “Remind
me in 30 minutes to switch the laundry,” and “Remind me tomorrow at 3 PM to call
John.” Relative minutes/hours and explicit today/tomorrow/weekday times are
supported. An unspecified or ambiguous time prompts for clarification. Listing
returns at most 20 incomplete items; spoken replies mention at most 10. Exact
unique title selection is required before completion or removal. Ambiguous matches
are never changed.

“Morning” means 9 AM, “afternoon” 3 PM, “evening” 7 PM, and “night” 8 PM.
“Tonight” means 7 PM today, if still in the future. These defaults are stated
in Kuzco's response so you can catch an unwanted time immediately. “On Monday
morning” selects the next Monday morning; if today is Monday and 9 AM has not
passed, it selects today.

The current utterance must explicitly authorize each operation. The deterministic
security policy validates the action and arguments before EventKit is called.
Reminder titles stay local and are retrieved only for a related request. They are
not added to greetings or general model context, and security logs contain action
metadata rather than titles.

Timers are deferred: Clock does not expose a verified supported set/inspect/cancel
interface suitable for this integration. Native Reminders handle their own alerts,
so the roadmap's separate notification phase should be reconsidered; it has not
been implemented here.
