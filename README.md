# Aura Frame Downloader

Bulk download photos from your Aura digital picture frame (auraframes.com). Aura provides no easy way to bulk download photos, so this tool lets you download all your photos at once. Since Aura stores photos on their servers, no physical access to the frame is needed.

---

## Download & Install (Easiest)

### macOS (Apple Silicon)

1. **Download** the latest release: [Aura-Downloader-macOS-arm64.zip](https://github.com/meub/aura-frame-downloader/releases/latest)

2. **Unzip** and drag `Aura Downloader.app` to your Applications folder

3. **First launch** - Right-click the app and select "Open" (required once since the app isn't signed by Apple)
   - If you see "app is damaged", run this in Terminal:
     ```bash
     xattr -cr "/Applications/Aura Downloader.app"
     ```

4. **Use the app:**
   - Enter your Aura email and password
   - Click "Add Frame" and enter your frame details (see [Getting your Frame ID](#getting-your-frame-id) below)
   - Select a download folder
   - Click "Start Download"

Your credentials and frame settings are saved automatically for next time.

### Windows

1. **Download** the latest release: [Aura-Downloader-Windows.zip](https://github.com/meub/aura-frame-downloader/releases/latest)

2. **Unzip** and run `Aura Downloader.exe`
   - Windows may show a SmartScreen warning since the app isn't signed
   - Click "More info" then "Run anyway"

3. **Use the app:**
   - Enter your Aura email and password
   - Click "Add Frame" and enter your frame details (see [Getting your Frame ID](#getting-your-frame-id) below)
   - Select a download folder
   - Click "Start Download"

Your credentials and frame settings are saved automatically for next time.

---

## Getting your Frame ID

1. Go to https://app.auraframes.com and log in
2. Click on the Frame name
3. Click on "View Photos" underneath the frame
4. Grab the ID from the URL: `https://app.auraframes.com/frame/<FRAME ID HERE>`

---

## Command Line Usage

If you prefer the command line or are on Windows/Linux:

### Setup

1. Install Python 3 and the requests module:
   ```bash
   pip install requests
   ```

2. Create a configuration file at:
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

### Commands

```bash
# Download photos from a frame
python download-aura-photos.py myframe

# Show photo count only
python download-aura-photos.py --count myframe

# Organize by year folders
python download-aura-photos.py --years myframe

# Use alternate config file
python download-aura-photos.py --config /path/to/config.ini myframe
```

### Options

| Option | Description |
|--------|-------------|
| `--config PATH` | Use alternate configuration file |
| `--count` | Show photo count and exit |
| `--years` | Organize photos into year subfolders |
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

The built executable will be at `dist\Aura Downloader.exe`.
