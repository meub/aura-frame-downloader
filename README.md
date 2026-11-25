# Aura Frame Downloader

Bulk download photos and videos from your Aura digital picture frame (auraframes.com). Aura provides no easy way to bulk download photos, so this tool lets you download all your photos at once. Since Aura stores photos on their servers, no physical access to the frame is needed.

---

## Download & Install (Easiest)

### macOS (Apple Silicon)

1. **Download** the latest release: [Aura-Downloader-macOS-arm64.zip](https://github.com/meub/aura-frame-downloader/releases/latest/download/Aura-Downloader-macOS-arm64.zip)

2. **Unzip** and drag `Aura Downloader.app` to your Applications folder

3. **First launch** - Right-click the app and select "Open" (required once since the app isn't signed by Apple)
   - If you see "app is damaged", run this in Terminal:
     ```bash
     xattr -cr "/Applications/Aura Downloader.app"
     ```

4. **Use the app:**
   - Enter your Aura email and password, then click "Sign In"
   - Pick your frame from the list (frames shared with you are included)
   - Photos are saved to `Pictures/Aura/<frame name>` unless you choose another folder
   - Click "Start Download"

Your credentials and settings are saved, and the app signs you in automatically next time.

### Windows

1. **Download** the latest release: [Aura-Downloader-Windows.zip](https://github.com/meub/aura-frame-downloader/releases/latest/download/Aura-Downloader-Windows.zip)

2. **Unzip** and run `Aura Downloader.exe`
   - Windows may show a SmartScreen warning since the app isn't signed
   - Click "More info" then "Run anyway"

3. **Use the app:**
   - Enter your Aura email and password, then click "Sign In"
   - Pick your frame from the list (frames shared with you are included)
   - Photos are saved to `Pictures/Aura/<frame name>` unless you choose another folder
   - Click "Start Download"

Your credentials and settings are saved, and the app signs you in automatically next time.

---

<a id="getting-your-frame-id"></a>
## Getting your Frame ID (only needed for the command line)

The app lists your frames after you sign in, so you only need the Frame ID for the command line, or for a frame that doesn't appear in the app's list (use "Add by ID..."). Pasting the whole address from step 4 also works.

1. Go to https://app.auraframes.com and log in
2. Click on the Frame name
3. Click on "View Photos" underneath the frame
4. Grab the ID from the URL: `https://app.auraframes.com/frame/<FRAME ID HERE>`

---

## Troubleshooting

### "Login failed: The email or password was incorrect."

Use the same email and password you use to sign in to the Aura app.

### "Couldn't reach Aura. Check your internet connection and try again."

The app couldn't connect to Aura's servers. Check that you're online. On a work network or VPN, try another network.

### "Lost the connection to Aura..."

The connection dropped during a download. Photos that finished are kept. Click "Start Download" again and it continues where it stopped.

### My frame isn't in the list

The list shows every frame on the Aura account you signed in with, including frames other people shared with you. Check that you signed in with the right account. You can also add a frame with "Add by ID..." (see [Getting your Frame ID](#getting-your-frame-id)).

### "Aura could not load this frame" or "Check that the Frame ID is correct"

This usually happens with a frame added by ID: the ID is wrong, or the account you signed in with can't see that frame. Pick the frame from the list instead, or check the ID.

### "Download Finished With Errors"

Some photos didn't download. Click "Start Download" again to retry them. Photos that already downloaded are skipped. Details are in `aura-downloader.log` in the download folder.

### How long does it take?

The app waits about 2 seconds between photos so Aura doesn't block it, so 5,000 photos take around 3 hours. You can stop and restart at any time without downloading anything twice.

### Where are my photos?

In `Pictures/Aura/<frame name>`, unless you chose another folder. Click "Open Folder" when the download finishes.

### Reporting a problem

[Open an issue](https://github.com/meub/aura-frame-downloader/issues) with the version you downloaded, your operating system, the exact error message, and the `aura-downloader.log` file from your download folder. Never post your password.

---

## Your data

Your email, password and settings are saved on your computer so the app can sign in automatically: in `~/Library/Preferences/com.auradownloader.AuraFrameDownloader.plist` on macOS, and in the registry under `HKEY_CURRENT_USER\Software\AuraDownloader\AuraFrameDownloader` on Windows. The password is not encrypted, so on a computer account other people use, uncheck "Remember password": the saved password is deleted, and the app asks for it each time you open it. Your email and password are only sent to Aura's own server (`api.pushd.com`, the same one the Aura app uses).

---

## Command Line Usage

If you prefer the command line, or you're on Linux:

### Setup

1. Download this repository (green "Code" button, then "Download ZIP") or clone it, and open a terminal in that folder.

2. Install Python 3 and the requests module:
   ```bash
   pip install requests
   ```

3. Create a configuration file at:
   - **Windows:** `%USERPROFILE%/etc/aura/credentials.ini`
   - **Mac/Linux:** `$HOME/etc/aura/credentials.ini`

   Example config:
   ```ini
   [login]
   email = myemail@gmail.com
   password = mypassword

   [myframe]
   file_path = ./images
   frame_id = abf53be3-b73d-4de3-98cd-cfd289bd82df

   [anotherframe]
   file_path = ./images-another-frame
   frame_id = b69ddd8d-bcad-483f-adf4-e15ff9a48c47
   ```

   `frame_id` can be the ID or the frame's full `app.auraframes.com` address (see [Getting your Frame ID](#getting-your-frame-id)).

### Commands

```bash
# Download photos from a frame
python download-aura-photos.py myframe

# Show photo count only
python download-aura-photos.py --count myframe

# Organize by year folders
python download-aura-photos.py --years myframe

# Only download video clips (skip stills)
python download-aura-photos.py --videos-only myframe

# Save raw API JSON to a file (for debugging)
python download-aura-photos.py --save-assets /tmp/aura-assets.json myframe

# Use alternate config file
python download-aura-photos.py --config /path/to/config.ini myframe
```

### Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Use alternate configuration file |
| `--count` | Show photo count and exit |
| `--years` | Organize photos into year subfolders |
| `--videos-only` | Only download video clips, skip still photos |
| `--save-assets FILE` | Write the raw asset JSON returned by the Aura API to FILE |
| `--debug` | Enable debug logging |

---

## Notes

- **Throttling:** The Aura API may throttle downloads. The script automatically waits between downloads, but you may need to restart it for large collections.

- **Resume support:** Already-downloaded photos are skipped, so you can safely restart the script.

- **Filename format:** `2012-04-15-03-15-04.000_B9A0E367-FA8D-4157-A090-7EE33F603312.jpeg`
  - Based on `taken_at` timestamp + unique `id` + original extension

- **Duplicates:** The same photo uploaded by different people will be downloaded separately. Consider running a duplicate finder afterward.

---

## Development

### macOS/Linux

```bash
# Install virtual environment with dependencies
make install

# Run the GUI
make run-gui

# Build macOS app
make build-mac

# Run linter
make lint
```

See `make help` for all available commands.

`make run-gui` uses the same saved settings as the installed app, so running a newer version from source also updates the installed app's settings.

### Windows (PowerShell)

```powershell
# Full build (install + build)
.\build_windows.ps1 -All

# Or step by step:
.\build_windows.ps1 -Install    # Create venv and install dependencies
.\build_windows.ps1 -Build      # Build the executable
.\build_windows.ps1 -Run        # Run GUI from source
.\build_windows.ps1 -Clean      # Remove build artifacts
```

The built executable will be at `dist\Aura Downloader.exe`. Use `-Clean -All` for release builds so a failed build can't leave the previous exe behind, and close Aura Downloader first: Windows can't replace the exe while it's running ("Cannot remove item").
