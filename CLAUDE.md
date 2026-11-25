# Aura Frame Downloader

Bulk downloader for the photos and videos on Aura digital picture frames, using Aura's undocumented API (`api.pushd.com`). Ships as a PyQt6 desktop app for macOS (Apple Silicon) and Windows, built with PyInstaller and distributed through GitHub Releases, plus a Python CLI (`download-aura-photos.py`). The repo is public and most users are non-technical; they report problems through GitHub issues. Read `README.md` for user-facing setup and troubleshooting.

Global rules (style, dependencies, deploy policy) live in `~/.claude`. Only project-specific
material belongs below.

## Commands

```sh
make install       # create ./venv (not .venv) from the pyenv default Python, install requirements.txt
make run-gui       # run the app from source (shares saved settings with the installed app, see Gotchas)
make build-mac     # dist/Aura Downloader.app
make test          # pytest, offline and offscreen; must pass before you finish
./venv/bin/prospector aura/core.py   # lint; prospector takes one path per run
./venv/bin/python download-aura-photos.py --count <frame-section>   # CLI, reads ~/etc/aura/credentials.ini
```

The Windows build runs on a separate Windows PC, from PowerShell in the repo folder:
`powershell -ExecutionPolicy Bypass -File .\build_windows.ps1 -Clean -All`

## Architecture

```
aura/
  core.py                  # all API and download logic; the GUI and CLI both call download_photos_from_aura()
  config.py                # credentials.ini parsing (CLI only)
  exceptions.py            # AuraError subclasses; their messages are shown to users as-is
  gui/main_window.py       # window: Sign In -> frame picker -> Save to folder -> Start Download
  gui/download_worker.py   # QThreads: SignInWorker (frame list), DownloadWorker (download + log file)
aura_gui.py                # GUI entry point
download-aura-photos.py    # CLI entry point
aura_gui.spec              # PyInstaller spec; also holds the macOS bundle version
build_windows.ps1          # Windows venv + build
```

Aura API, base `https://api.pushd.com/v5`, reverse engineered (there is no public spec):
- `POST login.json` returns `result.current_user.id` and `.auth_token`, sent as the `X-User-Id` and `X-Token-Auth` headers. A wrong email or password is HTTP 475 with a JSON `message`.
- `GET frames.json` returns `frames[]` with `id`, `name`, `num_assets`, including frames shared with the account.
- `GET frames/<id>/assets.json?side_load_users=false` returns every asset in one response. A `limit=1000` parameter used to cap it. A wrong ID returns `{"error": true, "message": "Not found"}`.
- Photos come from `https://imgproxy.pushd.com/<user_id>/<file_name>`; videos from each asset's `video_url`.

GUI settings use `QSettings("AuraDownloader", "AuraFrameDownloader")`: `~/Library/Preferences/com.auradownloader.AuraFrameDownloader.plist` on macOS, `HKCU\Software\AuraDownloader\AuraFrameDownloader` on Windows. Keys: `email`, `password` (plain text), `manual_frames`, `folders` (per frame id), `selected_frame_id`, and the checkbox flags. The 2.1.x keys `frames` and `selected_frame` are migrated once, then removed.

## Gotchas

### A frame ID containing "/" gets an HTML 404
The API's router answers `frames/https://app.auraframes.com/frame/<id>/assets.json` with an HTML page, which users saw as "Unexpected error: Expecting value: line 1 column 1 (char 0)" (issues #12, #21, fixed 2026-11-25 in 2.1.1). `normalize_frame_id()` pulls the UUID out of whatever was typed. Call it wherever a frame ID comes from user input.

### The packaged app has no console
The spec sets `console=False`, so log output goes nowhere unless a handler is attached. `DownloadWorker` writes each run to `aura-downloader.log` in the download folder (overwritten every run). Ask issue reporters for that file.

### Windows PowerShell doesn't stop when a native command fails
`$ErrorActionPreference = "Stop"` ignores the exit codes of python, pip and pyinstaller, and the script used to report "Build complete" because the previous exe was still in `dist`. The first v2.1.1 Windows upload was the stale 2.1.0 exe because of this (2026-11-25). `build_windows.ps1` now checks `$LASTEXITCODE` with `Assert-LastExit` and deletes the old exe before building. Commands given to the user for the Windows PC should be one line, with `throw` guards after each native command.

### Close the app before a Windows build
A running `dist\Aura Downloader.exe` locks the file, and `-Clean` fails with "Cannot remove item". An admin window doesn't help.

### `make run-gui` shares settings with the installed app
They use the same QSettings name, so running a newer version from source migrates the installed app's settings.

### `gh release edit --target` needs the full commit SHA
A short SHA is rejected ("Published releases must have a valid tag").

### GitHub doesn't start workflows for draft releases
That's why `build.yml` is started by hand (`workflow_dispatch` with a tag input) instead of by a release event.

### Actions' pwsh steps only fail on the last command
The wrapper checks `$LASTEXITCODE` once at the end, so a failed `pip install` followed by a successful command still passes. `build.yml` runs every step in bash, Windows included.

## Conventions

- User-facing error text is the exception message raised in `core.py`; it reaches the GUI dialog and the CLI unchanged. Write it for non-technical users, and keep the README Troubleshooting headings matching the real strings.
- The version is written in three places: `CFBundleVersion` and `CFBundleShortVersionString` in `aura_gui.spec`, and `__version__` in `aura/__init__.py`.
- Release zip names never change, because the README links to `releases/latest/download/<name>`: `Aura-Downloader-macOS-arm64.zip` (`.app` at the zip root) and `Aura-Downloader-Windows.zip` (`.exe` at the zip root).

## Release

Only when asked. Every step that touches GitHub needs the user's go-ahead.

1. Bump the version, commit, push `main`.
2. Create the draft with no files: `gh release create vX.Y.Z --draft --target <full sha> --title "vX.Y.Z - <summary>" --notes-file <notes>`. Notes follow the previous release's layout (What's New, macOS First Launch, Windows).
3. Build both zips on GitHub: `gh workflow run build.yml -f tag=vX.Y.Z`, then `gh run watch`. `.github/workflows/build.yml` builds the draft's target commit with Python 3.13, fails if the tag and the versions in `aura/__init__.py` and `aura_gui.spec` disagree, and attaches both zips to the draft. Without `-f tag=` it's a dry run that keeps the zips as run artifacts only.
4. Check the zips (see Verifying changes), then `gh release edit vX.Y.Z --draft=false`, and confirm both `releases/latest/download/...` links redirect to the new version.

Local builds still work as a fallback: `make build-mac`, then `ditto -c -k --keepParent "Aura Downloader.app" Aura-Downloader-macOS-arm64.zip` in `dist/`; on the Windows PC, one guarded PowerShell line that runs `build_windows.ps1 -Clean -All`, `Compress-Archive`, and `gh release upload vX.Y.Z dist\Aura-Downloader-Windows.zip --clobber` (the draft must exist first). The local Mac venv is Python 3.8, older than the workflow's 3.13.

## Verifying changes

- `make test` runs `tests/` (also run by `build.yml` before building). `conftest.py` fails any test that makes a real HTTP request and skips the download loop's sleeps; `helpers.py` has `make_response` and `FakeSession`. GUI tests run offscreen and point `main_window.QSettings` at a temp INI file (the `settings_path` fixture), so the real saved settings are never touched.
- For UI changes, also look at the window: `widget.grab().save(...)` offscreen, then view the PNG.
- Lint: compare prospector output against a `git stash` baseline. The existing warnings (too many arguments/statements, unused `DownloadError`, `unnecessary-pass`) are known.
- Built Mac app: `Info.plist` version, `codesign --verify --deep`, and an offscreen launch that stays up for a few seconds.
- Release zips: download them into an empty folder (`gh release download vX.Y.Z -D <dir>`), compare SHA-256 with the previous release, and confirm new code is inside with `CArchiveReader(exe).open_embedded_archive("PYZ.pyz").extract("aura.core", raw=True)`, searching the bytes for an identifier added in this release. For the Mac app, `exe` is `Aura Downloader.app/Contents/MacOS/Aura Downloader`.
