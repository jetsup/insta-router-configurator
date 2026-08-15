# Smalnets Router Configurator

Desktop application for configuring and managing MikroTik RouterOS devices in
the Smalnets hotspot network. It talks to the Smalnets API at
`https://smalnets.ddns.net`, tests router connectivity, and provisions
hotspot infrastructure on the router.

## Features

- Login and token-based authentication with the Smalnets API
- Connect to RouterOS devices over the RouterOS API (port 8728)
- Connection testing and router password management
- VPN / WireGuard tunnel setup
- RADIUS NAS registration and GenieACS integration
- Hotspot provisioning: bridge, DHCP, hotspot profile, NAT, walled garden, and
  captive-portal file upload
- Headless (CLI) provisioning of the same steps as the GUI wizard
- Automatic update checks against GitHub Releases
- Light and dark themes with system theme detection

## Requirements

- Python 3.12+
- A MikroTik RouterOS device on the same LAN (default `192.168.88.1`, user
  `admin`, API port `8728`)
- A Smalnets admin account with a saved API token (`~/.smalnets_token`)

Python dependencies are listed in [`config_program/requirements.txt`](config_program/requirements.txt).

## Quick Start

### GUI

```bash
pip install -r config_program/requirements.txt
python3 config_program/main.py
```

- Login with your Smalnets credentials
- Select an ISP and open the provisioning wizard
- Fill in the router IP, user, and password
- The wizard handles: identity, firewall, WireGuard, RADIUS, bridge-hotspot,
  DNS, walled garden, and file upload

### Headless provisioning

```bash
python3 scripts/provision_router.py
```

Runs the same steps as the GUI wizard without a GUI. Re-running it on the same
router reuses the existing VPN IP.

### Diagnostics

```bash
python3 scripts/diagnose_hotspot.py
```

Prints the router's current hotspot/bridge/firewall state.

## Usage

The configurator uses ethernet port 2 (LAN) on the router for provisioning. It is mandatory to connect to this port as any other port will not fully provision the router as they will be locked down during the provisioning process.

Ethernet port may be locked from the android app or the user dashboard after provisioning.

## Building

Standalone binaries are compiled with [Nuitka](https://nuitka.net/).

### Linux

```bash
sudo apt-get install -y build-essential libgl1-mesa-dev
./build_linux.sh [VERSION]        # e.g. ./build_linux.sh 1.0.0
```

Output: `dist/smalnets_<version>_<arch>.bin`

### Windows

```bat
build_windows.bat [VERSION]
```

Output: `dist\smalnets_<version>_amd64.exe`

The build scripts also generate the Windows `logo.ico` from the source PNG
(`scripts/make_icon.py`) so the executable and taskbar show the app logo.

## Releases & Updates

Release builds are produced by the GitHub Actions workflow
(`.github/workflows/build.yml`) for Windows, Linux (deb/rpm), and macOS, and
are attached to GitHub Releases. The app checks
`https://api.github.com/repos/jetsup/insta-router-configurator/releases/latest`
for new versions and offers to download and apply updates on Windows.

## Project Layout

```txt
assets/             App logo and icons
config_program/     PySide6 desktop application
scripts/            Headless provisioning, diagnostics, icon generation
test_rerun.py       Idempotency test against a live router
test_provision.py   Full provisioning test against a live router
build_linux.sh      Linux compile script (Nuitka)
build_windows.bat   Windows compile script (Nuitka)
```

## License

MIT
