# Weather and immediate Skills

Normal CLI/chat/voice/background mode uses the production `direct` routing policy.
It now runs Weather, Timekeeping and Greeting Skills before model residency or
inference. Explicit `--model` and experimental `--routing hybrid` retain their
diagnostic behavior. Compound/ambiguous requests fall back to the existing agent.

## Weather setup

The default is current macOS location, requested only for weather. Run the existing
locked setup first; `install_assets.py` now also builds the small native helper.
For an existing RC installation:

```sh
uv run --locked python weather_location.py --authorize
```

Use the same `KUZCO_HOME` as your installation. Allow **Kuzco Weather** when macOS
asks. Location Services must be enabled. No access to the Weather app's private
data is needed. The helper uses Core Location, one fix per weather request, a
six-second acquisition deadline, and ignores initial fixes over five minutes old or over
10 km in reported uncertainty while waiting for a usable update within that same deadline.
Updates stop at success/failure/timeout; there is no ongoing tracking. It rounds coordinates to two decimal places before
passing them to Python. No location history is stored. macOS location behavior
depends on OS services and network availability; a fresh fix is not guaranteed.

If location is denied/unavailable, Kuzco reports that and performs no forecast
request. It does not silently assume a home city or use IP geolocation. An optional
manual fallback can be explicitly configured in `KUZCO_HOME/config/weather.json`:

```json
{"latitude":40.71,"longitude":-74.01,"label":"New York"}
```

That example is not installed automatically. Delete that file or replace it with
`{"mode":"current"}` to use current location again. Restrict its permissions to
0600 if creating it. Location is configuration, not memory or credentials.

## Provider, privacy and interpretation

Open-Meteo's HTTPS forecast endpoint receives only approximate coordinates and
fixed forecast variable/unit/day selections. The provider also sees normal network
metadata such as source IP. No prompts, history, documents, secrets or personality
instructions are sent. Apple Location Services operates under macOS permission
and its own privacy behavior; this feature is not an offline geolocation promise.

The free endpoint is for non-commercial use and has rate limits/no availability
guarantee. No key or new Python dependency is required. Existing certifi provides
the TLS trust bundle. Requests reject redirects, ignore proxy environment settings,
have a five-second network timeout and 100 KB body limit, and do not retry. There is
no persistent weather cache. Data attribution: [Open-Meteo](https://open-meteo.com/),
[API documentation and terms](https://open-meteo.com/en/docs).

Current conditions, today/tonight/tomorrow, hourly high/low, precipitation chances,
umbrella/jacket/grilling interpretation use numeric fields only. Values are degrees
Fahrenheit and mph. Tonight means 6 PM to midnight at the returned forecast timezone.
Rain timing is the first remaining hourly probability of at least 30%, not a promise
of exact onset. Grilling/jacket guidance uses simple disclosed heuristics (30%
precipitation, 20 mph wind, 60°F jacket threshold) and is not severe-weather advice.
Forecast highs/lows are derived from available hourly temperatures. Missing/malformed
or stale current data fails closed. Source and update time remain in debug/history;
raw provider text cannot request another action. URLs are not spoken.

“What about tomorrow?” reuses only the immediately preceding weather intent, fetches
fresh data, and preserves an umbrella/rain/etc. question. An unrelated intervening
turn clears that context. In wake mode say Kuzco again for each follow-up; this does
not introduce always-listening conversation.

Greeting wording lives in replaceable personality JSON files. It composes alternatives
and avoids the immediately previous response, without optional network/context work.
Timekeeping reads the policy-protected clock on every request; timezone support is
limited to UTC, London, New York and Tokyo. No calendar capability is added.
