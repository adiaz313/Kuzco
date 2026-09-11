# Architecture and operating boundaries

`main.py` provides text CLI/chat and the bounded JSON agent loop. `routed.py`
selects narrow Python fast paths or resident Llama 3.1 8B. Experimental explicit
model selectors remain development-only; no automatic 1B/3B adoption.

`skills/` contains Web Research, Document Analysis and Mac Utility. Skills narrow
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

`background.py`, `service.py` and a small native launcher supply microphone
permission, sleep recovery and login startup. There is no full GUI. Personality
files are independent instructions and unchanged in this release candidate.

## Roadmap

Phases 1–11 complete; Sherpa retained after OpenWakeWord evaluation; Piper adopted.
Phase 12 constructs this candidate. Phase 13 will dogfood this actual installation,
including greeting/definition quality, RAG delays and Lions/web reliability.
Phase 14 is the eventual v1 publication decision. Neither is started automatically.
