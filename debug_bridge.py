"""Debug script to inspect bridge port data from RouterOS API."""
import sys

sys.path.insert(0, 'config_program')
from routeros.connector import RouterOSConnector

host = '192.168.88.1'
user = 'admin'
password = ''
port = 8728

conn = RouterOSConnector(host, user, password, port)
ok, msg = conn.connect()
if not ok:
    print(f'Connect failed: {msg}')
    sys.exit(1)
print(f'Connected: {msg}')

# Print all interfaces
print('\n=== INTERFACES ===')
ifaces = conn.cmd('/interface/print')
for i in ifaces:
    print(f"  name={i.get('name')}, type={i.get('type')}, running={i.get('running')}")

# Print all bridge ports with full structure
print('\n=== BRIDGE PORTS (raw) ===')
ports = conn.cmd('/interface/bridge/port/print')
print(f'Total ports: {len(ports)}')
for bp in ports:
    print(f'  type={type(bp).__name__}, keys={list(bp.keys())}')
    for k, v in bp.items():
        if isinstance(v, dict):
            print(f'    {k} -> dict: {list(v.keys())}')
        else:
            print(f'    {k} = {v!r} (type={type(v).__name__})')

# Print all bridges
print('\n=== BRIDGES ===')
bridges = conn.cmd('/interface/bridge/print')
for b in bridges:
    print(f"  name={b.get('name')}, vlan_filtering={b.get('vlan-filtering')}")

# Try to find interface and resolve
print('\n=== TESTING RESOLVE ===')
test_ifaces = ['ether3', 'ether4', 'ether5', 'wlan1']
for iface_name in test_ifaces:
    print(f'\nLooking for {iface_name} in bridge ports...')
    found = False
    for bp in ports:
        raw = bp.get('interface')
        resolved = raw
        if isinstance(raw, dict):
            resolved = raw.get('name', '')
        elif raw is not None:
            resolved = str(raw)
        else:
            resolved = ''
        if resolved == iface_name:
            print(f'  FOUND! port_id={bp.get(".id")}, bridge={bp.get("bridge")}, pvid={bp.get("pvid")}')
            found = True
            break
    if not found:
        print('  NOT FOUND in bridge ports')
        # Check if interface exists at all
        for i in ifaces:
            if i.get('name') == iface_name:
                print(f'  Interface exists, is bridge port? {i.get("port-type")}')

conn.disconnect()
