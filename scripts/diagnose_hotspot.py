#!/usr/bin/env python3
"""
RouterOS hotspot diagnostic tool.
Checks hotspot profile, server, bridge, files, and tests HTTP access.
"""
import sys
import urllib.error
import urllib.request

sys.path.insert(0, '/my-files/Creations/Projects/insta-billing/config_program')
from routeros.connector import RouterOSConnector


def diagnose(host: str, user: str, password: str, port: int = 8728):
    conn = RouterOSConnector(host, user, password, port)
    ok, msg = conn.connect()
    if not ok:
        print(f'FAIL: {msg}')
        return
    print(f'Connected: {msg}')
    results = {}

    # System identity
    identity = conn.cmd('/system/identity/print')
    results['identity'] = identity[0] if identity else {}
    print(f'\n=== Identity: {results["identity"].get("name", "?")} ===')

    # Hotspot profiles
    results['hotspot_profiles'] = conn.cmd('/ip/hotspot/profile/print')
    print(f'\n=== Hotspot Profiles ({len(results["hotspot_profiles"])}) ===')
    for p in results['hotspot_profiles']:
        print(f'  name={p.get("name")} html_directory={p.get("html-directory","")} dns_name={p.get("dns-name","")} use_radius={p.get("use-radius","")}')

    # Hotspot servers
    results['hotspot_servers'] = conn.cmd('/ip/hotspot/print')
    print(f'\n=== Hotspot Servers ({len(results["hotspot_servers"])}) ===')
    for s in results['hotspot_servers']:
        print(f'  name={s.get("name")} interface={s.get("interface")} profile={s.get("profile")} disabled={s.get("disabled")}')

    # Bridges
    results['bridges'] = conn.cmd('/interface/bridge/print')
    print(f'\n=== Bridges ({len(results["bridges"])}) ===')
    for b in results['bridges']:
        print(f'  {b.get("name")} comment={b.get("comment","")}')

    # Interfaces
    results['interfaces'] = conn.cmd('/interface/print')
    print('\n=== Interfaces (relevant) ===')
    for i in results['interfaces']:
        name = i.get('name', '')
        if any(x in name for x in ('bridge', 'wg', 'hotspot', 'ether', 'wlan')):
            print(f'  {name:20s} type={i.get("type",""):10s} running={i.get("running","")}')

    # IP addresses
    results['ip_addresses'] = conn.cmd('/ip/address/print')
    print('\n=== IP Addresses ===')
    for a in results['ip_addresses']:
        print(f'  {a.get("address"):20s} interface={a.get("interface")}')

    # WireGuard
    results['wireguard'] = conn.cmd('/interface/wireguard/print')
    print(f'\n=== WireGuard ({len(results["wireguard"])}) ===')
    for w in results['wireguard']:
        print(f'  {w.get("name")} running={w.get("running")}')

    # DHCP servers
    results['dhcp_servers'] = conn.cmd('/ip/dhcp-server/print')
    print(f'\n=== DHCP Servers ({len(results["dhcp_servers"])}) ===')
    for d in results['dhcp_servers']:
        print(f'  name={d.get("name")} interface={d.get("interface")} pool={d.get("address-pool")}')

    # NAT rules
    results['nat_rules'] = conn.cmd('/ip/firewall/nat/print')
    print(f'\n=== NAT Rules ({len(results["nat_rules"])}) ===')
    for n in results['nat_rules']:
        c = n.get('comment', '')
        if 'hotspot' in c or 'smalnets' in c:
            print(f'  chain={n.get("chain")} action={n.get("action")} comment={c}')

    # Walled garden
    results['walled_garden'] = conn.cmd('/ip/hotspot/walled-garden/print')
    print(f'\n=== Walled Garden ({len(results["walled_garden"])}) ===')
    for w in results['walled_garden']:
        print(f'  dst-host={w.get("dst-host","")} action={w.get("action")} server={w.get("server")}')

    # Walled garden IP
    results['walled_garden_ip'] = conn.cmd('/ip/hotspot/walled-garden/ip/print')
    print(f'\n=== Walled Garden IP ({len(results["walled_garden_ip"])}) ===')
    for w in results['walled_garden_ip']:
        print(f'  dst-address={w.get("dst-address","")} action={w.get("action")} dst-port={w.get("dst-port","")}')

    # Files listing (handle binary)
    raw = conn.ros.get_binary_resource('/file').call('print', {})
    results['files'] = []
    print('\n=== Files (hotspot-related) ===')
    for item in raw:
        decoded = {}
        for k, v in item.items():
            if isinstance(v, bytes):
                try:
                    decoded[k] = v.decode('utf-8')
                except UnicodeDecodeError:
                    decoded[k] = f'<binary:{len(v)} bytes>'
            else:
                decoded[k] = str(v)
        name = decoded.get('name', '')
        if 'hotspot' in name or name.startswith('ib/') or '/ib/' in name:
            results['files'].append(decoded)
            print(f'  {decoded.get("name"):40s} size={decoded.get("size","?"):>6s} type={decoded.get("type","")}')

    # HTTP check
    print('\n=== HTTP File Check ===')
    for path in ['/hotspot/login.html', '/ib/login.html']:
        try:
            url = f'http://{host}{path}'
            resp = urllib.request.urlopen(url, timeout=5)
            content = resp.read().decode('utf-8', errors='replace')
            has_custom = '$(link-login-only)' in content
            is_our = 'captive_portal_url' in content
            status = 'OUR TEMPLATE' if is_our else 'STOCK MIKROTIK' if has_custom else 'UNKNOWN'
            print(f'  {url}: HTTP {resp.status} — {status} ({len(content)} bytes)')
            if is_our:
                print(f'  First 300 chars: {content[:300]}')
        except urllib.error.HTTPError as e:
            print(f'  {path}: HTTP {e.code}')
        except Exception as e:
            print(f'  {path}: {e}')

    conn.disconnect()
    print('\n=== Diagnostic Complete ===')

    return results


if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else '192.168.88.1'
    user = sys.argv[2] if len(sys.argv) > 2 else 'admin'
    pw = sys.argv[3] if len(sys.argv) > 3 else ''
    port = int(sys.argv[4]) if len(sys.argv) > 4 else 8728
    diagnose(host, user, pw, port)
