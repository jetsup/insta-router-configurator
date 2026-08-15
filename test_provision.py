"""Test the full provisioning flow against the actual router."""
import sys

sys.path.insert(0, 'config_program')
from routeros.configurator import RouterOSConfigurator
from routeros.connector import RouterOSConnector

host = '192.168.88.1'
conn = RouterOSConnector(host, 'admin', '', 8728)
ok, msg = conn.connect()
if not ok:
    print(f'Connect failed: {msg}')
    sys.exit(1)
print(f'Connected: {msg}')

config = RouterOSConfigurator(conn)

# Clean up: remove old per-interface artifacts
print('\n=== CLEANUP old bridge-hotspot ports ===')
b_ports = conn.cmd('/interface/bridge/port/print')
hotspot_ifaces = ['ether3', 'ether4', 'ether5', 'wlan1']
for bp in b_ports:
    iface = bp.get('interface', '')
    br = bp.get('bridge', '')
    if iface in hotspot_ifaces and br != 'bridge':
        print(f'  Moving {iface} back to default bridge...')
        conn.cmd('/interface/bridge/port/set', numbers=bp.get('id'), bridge='bridge')
        print('  Moved')

# Provision the simple guest network
print('\n=== Provisioning guest network ===')
test_ifaces = [
    {'name': 'ether3'},
    {'name': 'ether4'},
    {'name': 'ether5'},
    {'name': 'wlan1'},
]
ok, result = config.provision_hotspot_ports(
    test_ifaces,
    dns_name='',
    radius_server_ip='10.200.0.1',
    router_id=1,
    stripped_name='fastnet',
)
if ok:
    print(f'  OK: {result}')
else:
    print(f'  FAIL: {result}')

# Verify
print('\n=== BRIDGE PORTS ===')
ports = conn.cmd('/interface/bridge/port/print')
for bp in ports:
    iface = bp.get('interface', '')
    br = bp.get('bridge', '')
    if iface in ['ether3', 'ether4', 'ether5', 'wlan1', 'bridge-hotspot']:
        print(f'  iface={iface} bridge={br}')

print('\n=== IP ADDRESSES on hotspot bridge ===')
addrs = conn.cmd('/ip/address/print')
for a in addrs:
    if 'bridge-hotspot' in a.get('interface', ''):
        print(f"  {a.get('address')} on {a.get('interface')}")

print('\n=== DHCP SERVERS ===')
dhcp = conn.cmd('/ip/dhcp-server/print')
for d in dhcp:
    print(f"  name={d.get('name')} iface={d.get('interface')} pool={d.get('address-pool')}")

print('\n=== HOTSPOT SERVERS ===')
hots = conn.cmd('/ip/hotspot/print')
for h in hots:
    print(f"  name={h.get('name')} iface={h.get('interface')} profile={h.get('profile')}")

print('\n=== HOTSPOT PROFILE ===')
profiles = conn.cmd('/ip/hotspot/profile/print')
for p in profiles:
    print(f"  name={p.get('name')} dns_name={p.get('dns-name')} radius={p.get('use-radius')}")

conn.disconnect()
