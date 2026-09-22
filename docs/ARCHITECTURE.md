# Architecture and operating boundaries

`main.py` provides text CLI/chat and the bounded JSON agent loop. `routed.py`
selects narrow Python fast paths or resident Llama 3.1 8B. Experimental explicit
model selectors remain development-only; no automatic 1B/3B adoption.

`skills/` contains bounded Web Research, Document Analysis, Mac Utility,
Reminders, Calendar, Maps/Places, Travel Time, Recommendations, Greeting,
Timekeeping, and Weather task layers. Skills narrow
instructions/tool availability; they never grant permissions. `security_policy.py`
authorizes every relevant tool/state action using trusted request scope. External
text, model decisions and personality cannot authorize privileged actions.

`web_search.py` isolates DDGS behind normalized evidence. `page_fetch.py` enforces
bounded public-HTTP retrieval and redirect/address checks; `page_extract.py`
cleans pages. `research.py` selects bounded multi-source evidence with provenance.
Requests and page URLs leave the Mac only for user-requested web retrieval. Web
content remains untrusted data. DDGS is free/no key, with no reliability guarantee.

`retrieval.py` reads the configured small local document collection. No private
collection ships. `memory.py` handles explicit remember/recall/update/forget
operations in SQLite, with policy checks and secret-pattern rejection. No automatic
LLM memory extraction, long-term conversation log or secret store.

`wake_input.py` + Sherpa detect Kuzco and endpoint speech; `speech_input.py` runs
local Whisper. `assistant_state.py` owns IDLE/LISTENING/THINKING/SPEAKING, and the
Swift indicator only renders it. `tts_output.py` selects Piper or explicit Daniel
fallback; only sanitized final answers are spoken. Audio processing stays local,
and temporary activated recordings are removed. Idle wake monitoring is explicit;
push-to-talk does not monitor while waiting. A shared lock prevents two listeners.

`calendar_read.py`, `reminders.py`, `maps_places.py`, and `mac_control.py` wrap
small fixed native helpers. They exchange bounded structured data; user/model
text never becomes executable source. Location and Calendar details are used
only for the active task and are not persisted as history.

`background.py`, `service.py` and a small signed native launcher supply microphone
permission, sleep recovery, login startup, and binary runtime status. The menu
master switch stops/starts the assistant child without controlling LM Studio.
There is no full GUI. Personality files are independent instructions.

## Release status

Kuzco v1.5.0 is the current release line. Sherpa remains the wake detector after
OpenWakeWord evaluation, and Piper is the default speech output. Historical phase
reports in `evaluation/` describe the development and release process as it stood
at the time; they are not instructions for the current installation.
