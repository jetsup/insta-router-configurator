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
