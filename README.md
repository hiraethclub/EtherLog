# EtherLog

A cross-platform desktop application for shortwave radio enthusiasts to compose,
log, and send electronic reception reports (eQSL).  Built with Python and PyQt5.

---

## Features

- Compose structured reception reports with SINPO rating
- Station autocomplete from EIBI schedule data and your own report history
- EIBI autofill for frequency, language, and target region
- Searchable, filterable report log with CSV export
- Printable airmail QSL address labels for postcard-based reception reports
- Built-in EIBI shortwave schedule database (updated on demand)
- SMTP email sending with full body preview
- Secure SMTP password storage via system keychain
- Light / Dark / System theme
- Data stored in the platform-appropriate user config directory

---

## Installing Dependencies

Requires Python 3.11 or later.

```bash
pip install -r requirements.txt
```

Dependencies:
- **PyQt5 ≥ 5.15** – GUI framework
- **platformdirs ≥ 3.0** – platform-appropriate config directory resolution
- **keyring ≥ 24.0** – system keychain integration for SMTP password storage

---

## First Run

```bash
python main.py
```

On first run the application opens the **Configuration** tab automatically.
You must create at least one Sender Profile (name, email address) before
sending reports.  SMTP settings are required before the Send via Email feature
will work.

---

## Configuring SMTP for Proton Mail Bridge

Proton Mail Bridge runs a local SMTP server on your machine.  Use these settings
in EtherLog's Configuration → SMTP Settings:

| Setting  | Value       |
|----------|-------------|
| SMTP Host| `127.0.0.1` |
| SMTP Port| `1025`      |
| Username | Your Proton Mail address |
| Password | The Bridge password (shown in the Bridge app) |
| Use STARTTLS | **Off** |
| Use SSL  | **Off**     |

Bridge handles encryption itself; EtherLog connects to it on localhost without
an additional TLS wrapper.

---

## Printing Airmail QSL Labels

For reception reports you post as physical QSL cards, EtherLog can generate a
self-adhesive airmail address label to stick on the postcard.

1. Store the station's postal mailing address in the **Station Postal Address**
   field on the New Report form (or in the Edit dialog on the Log tab).
2. Enter your own return address in **Configuration → Sender Profiles → Return
   Postal Address**.
3. On the **Log** tab, select the report and click **Print Airmail Label…**
   (also available from the right-click context menu).

The label composer shows a live preview and lets you:

- Edit the recipient and return addresses before printing.
- Choose a label size (Standard 90×50 mm, Large, Small, or Square).
- Toggle the classic red/blue **PAR AVION / BY AIR MAIL** border.
- Include or omit the return address.
- **Print…** to any connected printer, or **Save as PDF…** for later printing.

The recipient address is sized automatically to fit the chosen label.

---

## Updating the EIBI Station Database

Go to the **Station Database** tab and click **Update Database**.

EtherLog fetches the EIBI index page at `http://www.eibispace.de`, parses it to
find the current season's CSV link, then downloads and imports the schedule.  If
the index page is unavailable the app constructs the filename from the current
UTC date (season A = March–October, season B = November–February).

Custom stations you have added manually are never deleted or overwritten by an
EIBI update.

---

## SMTP Password and Keyring on Linux

EtherLog uses the `keyring` library to store the SMTP password in the system
keychain rather than in the plaintext config file.

On Linux, `keyring` requires a SecretService-compatible daemon:

- **GNOME** – GNOME Keyring is installed and running by default.
- **KDE** – KWallet with SecretService compatibility enabled.
- **Headless / minimal installs** – no keychain may be available.

If `keyring` cannot find a suitable backend, EtherLog will warn you and offer
to store the password in the config JSON file instead.  Only choose this option
if you understand that the password will be readable by any process running as
your user.

To install a keyring backend explicitly on Debian/Ubuntu:
```bash
sudo apt install gnome-keyring libsecret-tools
```

---

## PyInstaller Build

Requires PyInstaller 6.x:

```bash
pip install pyinstaller
pyinstaller etherlog.spec
```

The standalone executable is written to `dist/etherlog` (Linux/macOS) or
`dist/etherlog.exe` (Windows).

The spec file includes `hiddenimports` for keyring backends on all three
platforms.  If you encounter a `No module named 'keyring.backends.*'` error at
runtime, add the missing backend to the `_keyring_hidden` list in
`etherlog.spec` and rebuild.

## Releases (automated cross-platform builds)

Tagged releases are built automatically for Windows, macOS and Linux by the
`Release` GitHub Actions workflow (`.github/workflows/release.yml`).

The application version lives in a single place — `version.py` (`__version__`).
To cut a release:

1. Bump `__version__` in `version.py` (e.g. `1.0.0-beta.1`).
2. Commit to `main`.
3. Create and push a matching tag:
   ```bash
   git tag v1.0.0-beta.1
   git push origin v1.0.0-beta.1
   ```

The workflow then builds a standalone executable on each platform with
PyInstaller and publishes them to a GitHub Release. Any tag containing a
hyphen (`-beta`, `-rc`, …) is published as a **pre-release**.

Published assets:

| Platform | Asset |
|----------|-------|
| Windows  | `etherlog-windows-x86_64.exe` |
| macOS    | `etherlog-macos-arm64` |
| Linux    | `etherlog-linux-x86_64` |

---

### Platform notes

**Windows**: the executable runs without a console window (`console=False`).
You can add `icon="icon.ico"` to the `EXE()` call in the spec to set a custom
icon.

**macOS**: use `icon="icon.icns"`.  To create a `.app` bundle instead of a
single file, switch to the `BUNDLE()` construct in the spec.

**Linux**: the executable is a self-contained binary.  Users need no Python
installation but do need a running display server (X11 or Wayland with
XWayland).

---

## Data Storage

EtherLog stores all persistent data in the platform user config directory:

| Platform | Location |
|----------|----------|
| Windows  | `%APPDATA%\EtherLog\EtherLog\` |
| macOS    | `~/Library/Application Support/EtherLog/` |
| Linux    | `~/.config/EtherLog/` |

Files stored there:
- `config.json` – application settings (no password unless fallback is active)
- `etherlog.db` – SQLite database (reports, EIBI data, profiles)
