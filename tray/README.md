# Tray app (Phase 3+)

A small Python tray icon for Windows (`pystray`) that:

- starts the server and restarts it if it stops,
- shows the gate state as the icon color (red locked, green open),
- has Start session and End session in its right-click menu,
- sends Windows notifications ("2 quests left", "session running 2 h, add a note").

It talks to the server through the same API as the phone and never touches the database.
Until it exists, use `run.bat`.
