# Smalnets Router Configurator

Desktop application for configuring and managing MikroTik RouterOS devices in
the Smalnets hotspot network. It talks to the Smalnets API, tests router
connectivity, and provisions hotspot infrastructure on the router.

> The backend URL is set at **build time**. The configurator ships in two
> variants, each pointing at its own server, so a dev build can never be
> confused with a production one:
>
> | Variant | Backend            | Deployed to        |
> | ------- | ------------------ | ------------------ |
> | **prod** | `https://smalnets.com` | production server |
> | **dev**  | `https://smalnets.ddns.net` | development server |
>
> Binaries are named `*-dev*` for the dev variant. The in-app updater never
> offers a dev asset to a production install.

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
- Supports both legacy (Wave1 `wlan`) and new (**Wave2 `wifi`**) MikroTik radios

### WiFi radio support (Wave1 vs Wave2)

MikroTik ships two different radio stacks, and the tool detects which one a
router has and configures it accordingly:

| Radio     | Interface                       | Models                                   |
| --------- | ------------------------------- | ---------------------------------------- |
| **Wave1** | `/interface wireless` (`wlan1`) | Legacy devices — e.g. RB951Ui-2nD        |
| **Wave2** | `/interface wifi` (`wifi1`)     | Newer devices — e.g. L009UiGS-2HaxD      |

Wave2 replaced Wave1 on new hardware (RouterOS 7.13+). The L009UiGS-2HaxD (and
similar ax-capable models) expose `wifi1`, not `wlan1`, and reject the legacy
`/interface wireless` commands. The tool checks `/interface wifi` first and
falls back to `/interface wireless`, so the same wizard provisions both. Hotspot
networks are always configured as **open** (no WiFi password) — authentication
happens at the captive portal.

## Advanced device mode (why the tool asks for it)

RouterOS 7.x ships modern devices (e.g. the L009UiGS-2HaxD) in **home** mode
by default. In home mode MikroTik **disables hotspot, the firewall/NAT used by
the captive portal, and advanced interface options** — a router left in home
mode provisions partially but its hotspot never works and WiFi SSID changes
don't take effect.

The tool therefore checks the device mode before provisioning and prompts you
to switch the router to **Advanced** mode if it is in home mode. Do this from
the router:

```routeros
/system/device-mode/update mode=advanced
```

The router reboots to apply the change (the on-router notice says the new mode
applies on reboot). After it is back up, click **Next** in the tool and continue
as normal. The tool does not explain this inside the app so the on-screen
prompt stays simple; this section is where the reason lives.

> Home mode is stored only on disk, not flashed — it survives reboots. Once
> switched to advanced the router stays advanced.

## Prerequisites on the server

For a router's RADIUS traffic to reach FreeRADIUS the server must be set up
correctly (see the Insta Billing deployment guide):

1. **NAS clients in the `nas` table** of the FreeRADIUS `radius` database —
   one row per router `vpn_ip` with the matching `secret` and `shortname`.
   FreeRADIUS reads these **only at startup**, so `sudo systemctl restart
   freeradius` is required after adding rows (a `reload` is *not* enough).
2. **Firewall**: UDP ports **1812/1813** must be open to the VPN subnet, e.g.
   `sudo ufw allow 1812/udp` and `sudo ufw allow 1813/udp`. Without these the
   router logs "RADIUS server is not responding".
3. The router needs a **WireGuard tunnel to the server** so it can actually
   reach the RADIUS port (provisioned automatically by this tool).

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
- If prompted, switch the router to **Advanced** mode and wait for the reboot
  (newer devices ship in home mode — see the section above; the wizard will not
  proceed until the mode is advanced)
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

The provisioning order handled by the tool reproduces the deployment guide:
identity → firewall → WireGuard → RADIUS → (WiFi SSID, open network) →
hotspot bridge → walled garden/NAT → captive-portal file upload → WireGuard
peer registration on the server. Re-running on an already-provisioned router is
idempotent — existing config is detected and reused instead of duplicated.

## Troubleshooting

- **"RADIUS server is not responding" on the router** — the router reached the
  server but got no answer. Check that the server allows UDP 1812/1813
  (`sudo ufw status`), that a `nas` row exists for this router's VPN IP, and
  that FreeRADIUS was **restarted** after the row was added (it only reads the
  `nas` table at startup).
- **The router reboots when you switch device mode** — expected; the new mode
  applies on reboot. Wait for it to come back up, then continue the wizard.
- **WiFi SSID change has no effect on a new device (L009 etc.)** — it is Wave2:
  the tool configures `wifi1` via `/interface wifi`. Do not fall back to the
  legacy `/interface wireless` commands on these models.
- **Provisioning looks right but hotspot does not block** — verify the router
  is in **advanced** mode (see above); home mode disables hotspot/firewall
  silently.

## Building

Standalone binaries are compiled with [Nuitka](https://nuitka.net/). The build
scripts build for either the **prod** server (`https://smalnets.com`,
`root@102.68.87.210`) or the **dev** server (`https://smalnets.ddns.net`,
`root@84.247.164.42`), auto-increment the version from the latest git tag, and
can push the release tag and upload the binary to the server's release
folders:

### Linux

```bash
sudo apt-get install -y build-essential libgl1-mesa-dev
./build_linux.sh                       # prod build, v0.0.6 -> v0.0.7
./build_linux.sh --env dev             # dev build (backend https://smalnets.ddns.net)
./build_linux.sh --env both            # prod + dev binaries, both kept
./build_linux.sh --env dev --upload    # build dev + scp to the dev server
./build_linux.sh --version 1.2.3       # force a specific version
./build_linux.sh --no-tag              # build but do not create/push the git tag
./build_linux.sh --help                # full option reference
```

Output: `dist/smalnets_<version>_<arch>.bin` (prod) /
`dist/smalnets_<version>-dev_<arch>.bin` (dev).

Nuitka's working directories are kept on disk so both variants survive a
`both` run: the prod build lives in `build/` and the dev build in
`build/dev/`. (Only each variant's own `main.*` artifacts are cleared
before it builds, so `build/dev/` is never wiped by a prod build.)

### Windows

```bat
build_windows.bat                       rem prod build, v0.0.6 -> v0.0.7
build_windows.bat --env dev             rem dev build
build_windows.bat --env both            rem prod + dev binaries, both kept
build_windows.bat --env dev --upload    rem build dev + scp to the dev server
build_windows.bat --version 1.2.3       rem force a specific version
build_windows.bat --no-tag              rem build without tag push
build_windows.bat --help                rem full option reference
```

Output: `dist\smalnets_<version>_amd64.exe` (prod) /
`dist\smalnets_<version>-dev_amd64.exe` (dev).

Nuitka's working directories are kept on disk so both variants survive a
`both` run: the prod build lives in `build\` and the dev build in
`build\dev\`.

### Versioning, tags and uploads

* With no `--version` the script reads the most recent `vX.Y.Z` git tag and
  auto-increments the **patch** number (`v0.0.6` -> `0.0.7`); the new version
  is written to `config_program/version.txt` and embedded in the file name.
* Unless `--no-tag` is given, the script creates a `vX.Y.Z` tag from the
  current `HEAD` and **pushes it** — this mirrors the GitHub Actions flow,
  which builds all platforms and deploys on tag push. If the tag already
  exists it is not re-created.
* `--upload` scp's the built binary over SSH to the matching server's
  release folders (`releases/<tag>/` and `releases/latest/`). Upload
  requires the OpenSSH `ssh`/`scp` clients and a `deploy_config` file with
  your server credentials:

  ```bash
  cp deploy_config.sample deploy_config   # then edit the usernames/IPs
  ```

  The file holds `PROD_USER`/`PROD_HOST`, `DEV_USER`/`DEV_HOST` and
  `UPLOAD_BASE` (leave `DEV_*` empty if you have no dev server). It is
  git-ignored, so credentials stay out of the repository.

The build scripts also generate the Windows `logo.ico` from the source PNG
(`scripts/make_icon.py`) so the executable and taskbar show the app logo.

## Releases & Updates

Release builds are produced by the GitHub Actions workflow
(`.github/workflows/build.yml`) for Windows, Linux (deb/rpm), and macOS, and
are attached to GitHub Releases. Every tag builds **both** variants and deploys
each to its own server (prod to the production server, dev to the development
server). The app checks
`https://api.github.com/repos/jetsup/insta-router-configurator/releases/latest`
for new versions and offers to download and apply updates on Windows. The
updater only matches assets from the same variant it was compiled for, so a
production install never receives a `-dev` binary.

This repository has **immutable releases** enabled, so assets can only be
attached before a release is published. The workflow therefore triggers on a
**tag push**: it creates a draft release for the tag, attaches all installers
to it, then publishes it automatically.

To ship a release, just tag and push:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The workflow builds all installers, attaches them to the draft release, and
publishes it once every build succeeds. If a build fails, the release stays a
draft (so nothing broken is ever published). Do not publish a release manually
before the workflow has attached its assets.

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
