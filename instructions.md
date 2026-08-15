# Smalnets MikroTik Hotspot Provisioning

## Prerequisites

- RouterOS device with factory defaults (or clean state)
- Dev machine on same LAN as the router with Laravel server running
- Admin user with saved API token (`~/.smalnets_token`)

## Quick Start

```bash
# 1. Run headless provisioning
python3 scripts/provision_router.py

# 2. Verify configuration
python3 scripts/diagnose_hotspot.py

# 3. Connect a client to a hotspot port (ether3–ether5 or wlan)
#    The captive portal should redirect to http://$APP_URL/c/r1.portal
```

## Manual Steps (if needed)

### 1. Start the Laravel dev server

```bash
php artisan serve --host=0.0.0.0 --port=9000
```

The server MUST listen on `0.0.0.0` (all interfaces) so hotspot clients behind the router's NAT can reach it.

### 2. Provision with the GUI wizard

```bash
python3 config_program/main.py
```

- Login, select ISP, open the wizard
- Fill in router IP (`192.168.88.1`), user (`admin`), password (empty)
- The wizard handles: identity, firewall, WireGuard, RADIUS, bridge-hotspot, DNS, walled garden, file upload

### 3. Provision headlessly (no GUI)

```bash
python3 scripts/provision_router.py
```

This does the same steps as the wizard but from the CLI. Re-run on the same router reuses the existing VPN IP.

## How It Works

### Architecture

```text
[Hotspot Client] --(eth3-5/wlan1)--> [bridge-hotspot (192.168.10.0/24)]
     |                                         |
     |  DNS + HTTP intercepted                router routes + NAT
     v                                         v
[Router hotspot login page] <---------> [bridge (192.168.88.0/24)]
     |                                         |
     |  meta refresh                           |
     v                                         v
[Laravel server at $APP_URL/c/r1.portal] <----+
```

1. Client connects to hotspot → gets IP from DHCP pool (192.168.10.x)
2. Any HTTP request is intercepted by hotspot → serves `ib/login.html`
3. `login.html` has `<meta refresh>` redirecting to `http://$APP_URL:9000/c/r1.portal?mac=$(mac)&ip=$(ip)...`
4. Client's browser follows the redirect → reaches Laravel captive portal
5. User selects a plan → pays via M-Pesa (Daraja STK push) → RADIUS user created
6. Client gets internet access

### Key Components

| Component                 | Path                                                          | Purpose                                              |
| ------------------------- | ------------------------------------------------------------- | ---------------------------------------------------- |
| Hotspot login template    | `resources/views/hotspot/login.blade.php`                     | Redirects to Laravel portal                          |
| Hotspot alogin template   | `resources/views/hotspot/alogin.blade.php`                    | "Connected!" page after auth                         |
| Hotspot status template   | `resources/views/hotspot/status.blade.php`                    | Session status page                                  |
| API endpoint (serve HTML) | `GET /api/v1/hotspot/files?domain=...&captive_portal_url=...` | Renders Blade views to HTML                          |
| Upload method             | `RouterOSConfigurator.upload_hotspot_files()`                 | Uploads via `/file/add` to `ib/` dir                 |
| Provisioning logic        | `RouterOSConfigurator.provision_hotspot_ports()`              | Creates bridge, hotspot, profile, NAT, walled garden |
| Captive portal controller | `CaptivePortalController`                                     | Handles plan selection, payment, RADIUS              |
| Headless provisioner      | `scripts/provision_router.py`                                 | CLI equivalent of the GUI wizard                     |
| Diagnostic tool           | `scripts/diagnose_hotspot.py`                                 | Prints router state                                  |

### RouterOS API Notes

- Parameter names use underscores in Python but RouterOS expects hyphens.
- The `routeros_api` library passes parameter keys as-is (no underscore→hyphen mapping).
- **Hotspot profile**: `html_directory` → RouterOS `html-directory` — we set `html_directory='ib'`.
- **File operations**: `/file/remove numbers=<.id>` uses `.id` from `/file/print`.
- **Binary content**: `/file/print` may return binary `contents` field — the connector now handles decode errors with `errors='replace'`.
- **Custom upload directory**: Files are uploaded to `ib/` (not `hotspot/`) to avoid conflicts with RouterOS auto-generated stock hotspot files.

## Troubleshooting

### "file already exists" when uploading

RouterOS auto-generates stock hotspot files when the hotspot is first enabled. The provisioning uploads to a custom directory (`ib/`) to avoid this. If you still hit this, remove the old files first:

```routeros
/file remove [find name~"^ib/"]
```

### ERR_CONNECTION_REFUSED after redirect

1. Ensure `APP_URL` host:port is in the hotspot walled garden — the provisioning now adds this automatically via the `captive_portal_server` parameter.
2. Ensure the Laravel dev server listens on `0.0.0.0` (`--host=0.0.0.0`).
3. Verify the router can reach your dev machine: `/tool/fetch url="http://$APP_URL/api/v1/user" mode=http dst-path=/dev/null`

### {"error":"Forbidden","code":404}

The route `c/{router:captive_portal_url}` does implicit model binding on `routers.captive_portal_url`. If this column is empty, the route returns 404. The provisioning script now syncs it via `storeHotspots()` API endpoint.

Fix: `UPDATE routers SET captive_portal_url = 'rX.portal' WHERE id = <id>;`

### Multiple hotspot records in DB

Each provisioning run creates a new `Hotspot` record via `updateOrCreate`. Old records from prior runs with different `captive_portal_url` values remain — delete stale ones via the Hotspot model or directly.

## Testing End-to-End

1. Start the Laravel server: `php artisan serve --host=0.0.0.0 --port=9000`
2. Provision the router: `python3 scripts/provision_router.py`
3. Verify: `python3 scripts/diagnose_hotspot.py`
4. Connect a device to ether3, ether4, ether5, or wlan1 on the router
5. The device should get a 192.168.10.x IP via DHCP
6. Open a browser — it should redirect to `http://192.168.88.251:9000/c/r1.portal`
7. Select a plan and complete payment
