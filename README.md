# EtherLog

A cross-platform desktop application for shortwave radio enthusiasts to compose,
log, and send electronic reception reports (eQSL).  Built with Python and PyQt5.

---

## Features

- Compose structured reception reports with SINPO rating
- Station autocomplete from EIBI schedule data and your own report history
- EIBI autofill for frequency, language, and target region
- Searchable, filterable report log with CSV export
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
