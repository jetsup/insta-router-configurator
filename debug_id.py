"""Debug script to check .id vs id key across different API resources."""
import sys

sys.path.insert(0, 'config_program')
from routeros.connector import RouterOSConnector

host = '192.168.88.1'
conn = RouterOSConnector(host, 'admin', '', 8728)
ok, msg = conn.connect()
if not ok:
    print(f'Connect failed: {msg}')
    sys.exit(1)
print(f'Connected: {msg}')

# Check .id key in different resources
resources = [
    '/interface/bridge/port/print',
    '/interface/print',
    '/user/print',
    '/radius/print',
    '/ip/hotspot/profile/print',
]

for res in resources:
    print(f'\n=== {res} ===')
    try:
        data = conn.cmd(res)
        print(f'  count: {len(data)}')
        if data:
            item = data[0]
            has_dot_id = '.id' in item
            has_id = 'id' in item
            print(f'  has .id: {has_dot_id}, has id: {has_id}')
            print(f'  .id value: {item.get(".id", "N/A")!r}')
            print(f'  id value: {item.get("id", "N/A")!r}')
    except Exception as e:
        print(f'  ERROR: {e}')

# Also test bridge port remove with id
print('\n=== TEST BRIDGE PORT REMOVE ===')
ports = conn.cmd('/interface/bridge/port/print')
for bp in ports:
    iface = bp.get('interface', '')
    if iface == 'ether3':
        port_id = bp.get('id')
        print(f'  ether3: port_id={port_id!r} (type={type(port_id).__name__})')
        print(f'  Attempting remove with numbers={port_id!r}...')
        try:
            conn.cmd('/interface/bridge/port/remove', numbers=port_id)
            print('  Remove succeeded!')
        except Exception as e:
            print(f'  Remove failed: {e}')
        break

# Verify ether3 is now free
ports2 = conn.cmd('/interface/bridge/port/print')
ether3_found = any(bp.get('interface') == 'ether3' for bp in ports2)
print(f'  ether3 still in bridge ports: {ether3_found}')

# Re-add ether3 to bridge-hotspot
print('\n=== RE-ADDING ether3 ===')
try:
    result = conn.cmd('/interface/bridge/port/add', interface='ether3', bridge='bridge-hotspot')
    print(f'  Add result: {result}')
except Exception as e:
    print(f'  Add failed: {e}')

conn.disconnect()
