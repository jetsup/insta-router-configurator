# Smalnets MikroTik Configurator — Known Issues & Fixes

Deployment gotchas hit when provisioning real routers (we ran these live
against the RB951 and the L009). Read this before deploying to a new site.

---

## 1. Captive portal never auto-triggers (most common)

**Symptom:** Phone connects to the hotspot (gets `192.168.10.x`) but no page
appears; browsing works to the sink hosts but no login is forced. The known-good
reference router (RB951) triggers reliably; the new router (L009) does not.

**Root causes, in order of likelihood:**

1. **Missing stock hotspot template files.** The router only needs the 3 custom
   pages (`login.html`, `alogin.html`, `status.html`) to *display* the portal,
   but it needs the **full stock template set** — `redirect.html`,
   `rlogin.html`, `logout.html`, `error.html`, `radvert.html`, `errors.txt`,
   `md5.js`, `api.json`, `css/style.css`, `img/*.svg`, `xml/*` — for the
   redirect chain that *auto-forces* the portal. Without those, the phone's
   connectivity check to the sink name succeeds locally and never redirects.
   - Fix: ensure the server's `/api/v1/hotspot/files` returns the full set
     (`MikrotikService::hotspotTemplateFiles()` in insta-billing), and that
     `upload_hotspot_files()` uploads all of them.

2. **DNS statics with bare hostnames instead of `http://`-prefixed URLs.**
   The static entries must be the full URL, e.g.
   `http://connectivitycheck.android.com/generate_204` → `192.168.10.1`
   (see `CAPTIVE_PORTAL_DOMAINS`). A bare `connectivitycheck.android.com`
   does NOT rewrite the phone's DNS answer the same way; the connectivity
   check then resolves publicly and the portal is skipped.
   - Do **not** strip the `http://` prefix from the sink names — that was
     tried and reverted; the prefixed form matches the working RB951 exactly.

3. **Missing walled-garden entries.** The sink hosts and the portal server must
   be in the walled garden (`action=allow` for IP/host and `action=accept` for
   the portal IP:443). Checked on the RB951: one `smalnets-dns-*`,
   `smalnets-cp-*`, and `smalnets-radius*` entry per domain. See
   `_add_captive_portal_detection` and the `provision_hotspot_ports` block.

**Quick verification on the router:**

```routeros
/ip/dns/static/print          # names must start with http://
/ip/hotspot/walled-garden/print
/file print                   # smalnets dir must contain the full set
```

## 2. HTML directory differs between OS versions

RouterOS 6 routers (RB951) store hotspot files under **`flash/smalnets/`**,
RouterOS 7 routers (L009) under **`smalnets/`**. The profile must point to the
same dir the files are uploaded to, or the portal serves stale/empty content.

`_detect_hotspot_dir()` inspects `/file/print`: if any entry is `flash` or
starts with `flash/`, it returns `flash/smalnets/`, else `smalnets/`.

**Fix:** never hardcode the dir. Both `upload_hotspot_files()` (upload path)
and `provision_hotspot_ports()` (`html_directory=` on the profile) must use
`_detect_hotspot_dir()`. The html-dir must match what RB951 uses
(`flash/smalnets`) or what L009 uses (`smalnets`) respectively.

## 3. "file already exists" / stale files on re-upload

RouterOS will not let you `/file/add` over an existing file. Re-provisioning
onto a previously-provisioned router fails.

**Fix:** `upload_hotspot_files()` (and `router_settings_view.py` Step 10)
remove **all** existing files under the detected hotspot dir first, skipping
entries whose type is a directory, then upload the full set cleanly:

```routeros
/file remove [find name~"^smalnets/"]
```

Keyed removals prefer the `.id` from `/file/print` per name.

## 4. `/file/add` nested paths — no explicit mkdir needed

Previously we feared nested uploads (`css/`, `img/`, `xml/`) needed an explicit
`/file/add name=... type=directory`. Verified live on the L009 via the API
relay: `/file/add` with `smalnets/zzz-test/sub.html` **auto-creates the parent
directory** (`smalnets/zzz-test` shows as `type=directory`). Just upload the
files; subdirectories are created implicitly.

## 5. routeros-api `/file/print` returns bytes, not str

The `routeros_api` library returns dicts with **string keys** and **bytes
values** on `/file/print`. `row.get('name')` is bytes; comparing it against a
str silently fails. The connector already decodes with `errors='replace'`.

When debugging file listings, decode explicitly:

```python
name = (row.get('name') or b'').decode('utf-8', 'replace')
```

## 6. RADIUS reachability during provisioning

The router-side RADIUS config needs the **server VPN IP as seen from the
router**. Provisioning uses `radius_server_ip` (from the wizard, e.g.
`10.200.0.1` = network+1 of the router's VPN subnet). See
`provision_hotspot_ports()`: it adds the walled-garden allow entries
(`smalnets-radius`, `smalnets-radius443`, `smalnets-radius-dns`) and
`configure_radius()` adds `/radius` with the shared secret.

If the router reports "RADIUS server is not responding":

- Confirm the secret matches `RADIUS_SECRET` on the server.
- Confirm the FreeRADIUS `nas` row exists for the router's **VPN IP** (`nasname`)
  and that FreeRADIUS was **restarted** after inserting it (SQL `nas` clients
  are only read at startup — see `DEPLOY_ISSUES.md` §1 in insta-billing).
- Confirm UDP 1812/1813 are open on the server.

## 7. SSH relay / API access notes

- Router API access from the relay host may need `routeros_api` installed with
  `--break-system-packages` on the relay server (PEP 668).
- When running `sshpass -e ssh ...` in scripts, append `< /dev/null` so the
  remote command doesn't hang on a waiting stdin.
- Legacy RouterOS 6 routers may change their password via the web UI; the RB951
  used different credentials after its factory reset. Keep router passwords in
  sync with the tool before provisioning.

## 8. Controller/`router_controller` upload flow

The configurator's upload path is:
`router_controller._do_upload_hotspot_files` → `api.client.get_hotspot_files`
(GET `/api/v1/hotspot/files`) → `upload_hotspot_files()` stamps the returned
`dict[str,str]` onto the router. If the tool ever shows a partial set, check
the server's `/api/v1/hotspot/files` response first (it must include the full
template set, §1).

---

## Reference: working RB951 facts (known-good baseline)

| Item | RB951 value |
| --- | --- |
| Ident | `admin` / set after factory reset |
| DNS statics | `http://`-prefixed sink names (see `CAPTIVE_PORTAL_DOMAINS`) |
| Walled garden | one `smalnets-dns-*` + `smalnets-cp-*` per domain, `smalnets-radius*` |
| html-dir | `flash/smalnets` |
| RADIUS server | first usable VPN IP (`10.200.0.1`), secret matches server |
