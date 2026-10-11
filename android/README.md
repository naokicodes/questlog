# Android companion (Phase 4)

Kotlin + Jetpack Compose, sideloaded (not on the Play Store). Three jobs:

1. **Usage upload.** WorkManager every 15 min reads `UsageStatsManager` and posts daily totals to
   `POST /api/phone/usage`.
2. **Gate poller.** Reads `GET /api/gate` every 60 s while the screen is on and caches the result
   for up to 6 hours. After that with no server contact, it fails closed (locked).
3. **Blocker.** An `AccessibilityService` that sends you home and shows the block screen when you
   open a blocklisted app while the gate is locked. Emergency unlock uses
   `POST /api/gate/emergency`.

All requests send `Authorization: Bearer <phone token>` (create one with `phone-access.bat`).
The server URL and token are entered in the app's settings screen, never built into the APK.

Setup gotchas: enable Usage access, allow restricted settings (Android 13+) before turning on the
accessibility service, and turn off battery optimization for the app.
