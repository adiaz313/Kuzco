# Menu Bar Status and Master Control

Kuzco's existing signed background host owns a small native macOS menu-bar item.
It is a lifecycle control and status surface, not another assistant process.

The menu reports:

- **Kuzco — Running, Paused, or Not Running.** Running means the host's one
  Python assistant child is alive. Paused means the user switched Kuzco off.
- **Wake Word — On or Off.** On requires a private runtime signal from that
  exact child confirming that its microphone wake listener is currently open.
- **Local Model — Available or Unavailable.** The host checks LM
  Studio's local model inventory every 15 seconds and whenever the menu opens.
  This never invokes the model.

Operational rows use normal dynamic macOS label text. Green means active and
healthy, red means a required component is unavailable, and neutral means
intentionally paused/off. A reachable configured model is green whether it is
currently loaded or idle.

`Kuzco Enabled` is a native macOS switch and the real master control. Turning it off stops the existing
assistant child, releases the microphone/wake listener, and leaves only the
lightweight menu host. Turning it on starts exactly one child. The choice is
kept in the private Kuzco data directory and survives host restarts.

`Quit Kuzco` stops the assistant and unloads its LaunchAgent for the current
login session so launchd does not immediately respawn it. The installed login
configuration remains in place; `python service.py start` restores it, and a
normal future login can start it again.

The source artwork is preserved byte-for-byte at
`assets/kuzco-menu-icon-source.png`. The menu uses the separately derived
`assets/kuzco-menu-icon-statusbar.png`; future visual changes must never
overwrite the source image.

The menu records only bounded lifecycle messages. Runtime status contains a
PID, listener boolean, and timestamp with owner-only permissions. It contains
no transcript, audio, current location, calendar data, document content, model
prompt, or credentials.
