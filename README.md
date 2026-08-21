# TrinityX (Flutter scaffold)

A starting mobile dashboard for the options engine in this repo. `flutter create`
was never run locally here, so the `android/` folder doesn't exist yet —
Codemagic generates it automatically on first build (see below), or you
can generate it yourself if running locally.

## Getting your APK (Codemagic, free tier)

1. Put these files at the root of a repo (this replaces the old broken
   `codemagic.yaml` if reusing `trinityxstockoption` — or push to a new repo).
2. Push to GitHub.
3. Sign in at codemagic.io with GitHub and add the repo.
4. Codemagic detects `codemagic.yaml` and runs `android-workflow`
   automatically. First build takes ~5–10 min.
5. Download the `.apk` from the build's **Artifacts** tab.

If you'd rather keep this inside the same repo as your Python engine,
put these files in a subfolder (e.g. `mobile/`) and prefix each script
in `codemagic.yaml` with `cd mobile &&`.

## Running locally

If you have Flutter installed:

```bash
flutter create --platforms=android --org com.trinityx .
flutter pub get
flutter run
```

That first command only needs to run once. After a build succeeds —
on Codemagic or locally — commit the generated `android/` folder and
remove it from `.gitignore`, so future builds stop regenerating it
from scratch and any manual tweaks (icons, permissions, signing) stick.

## What's here

- `lib/screens/dashboard_screen.dart` — capital, risk limits, and a
  live session-window strip, all sourced from
  `lib/models/strategy_config.dart` (hand-mirrored from `config.py` —
  update both when you change one).
- `lib/screens/positions_screen.dart` — empty state, ready to wire to
  a `GET /positions` endpoint on your FastAPI layer.
- `lib/screens/settings_screen.dart` — full strategy parameter list.

## Not done yet

- No network calls anywhere — Positions is a placeholder.
- No Kite Connect login screen.
- The live session check assumes the device clock is already IST.
- No custom app icon or `applicationId` — both come from Flutter's
  defaults until you set them in `android/app/build.gradle` after the
  first generated build.
