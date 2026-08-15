"""Test idempotency of the simplified guest network provisioning."""
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

test_ifaces = [
    {'name': 'ether3'},
    {'name': 'ether4'},
    {'name': 'ether5'},
    {'name': 'wlan1'},
]

print('\n=== SECOND RUN (should be idempotent) ===')
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

print('\n=== VERIFY BRIDGE PORTS ===')
ports = conn.cmd('/interface/bridge/port/print')
for bp in ports:
    iface = bp.get('interface', '')
    br = bp.get('bridge', '')
    if iface in ['ether3', 'ether4', 'ether5', 'wlan1']:
        print(f'  {iface}: bridge={br}')

print('\n=== VERIFY HOTSPOT PROFILE ===')
profiles = conn.cmd('/ip/hotspot/profile/print')
for p in profiles:
    if p.get('name') != 'default':
        print(f"  name={p.get('name')} dns_name={p.get('dns-name')}")

conn.disconnect()
