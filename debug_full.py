"""Test full bridge port add + PVID flow."""
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

def print_bridge_ports(label=''):
    if label:
        print(f'\n--- {label} ---')
    ports = conn.cmd('/interface/bridge/port/print')
    for bp in ports:
        iface = bp.get('interface', '')
        br = bp.get('bridge', '')
        pid = bp.get('id', '')
        pvid = bp.get('pvid', '')
        print(f'  id={pid} iface={iface} bridge={br} pvid={pvid}')

# Show current state
print_bridge_ports('BEFORE')

ifaces = ['ether3', 'ether4', 'ether5', 'wlan1']
for vlan_offset, iface in enumerate(ifaces):
    vlan_id = 30 + vlan_offset * 10
    print(f'\n=== {iface} → VLAN {vlan_id} ===')

    # Remove from current bridge
    ports = conn.cmd('/interface/bridge/port/print')
    for bp in ports:
        b_iface = bp.get('interface', '')
        if b_iface == iface:
            pid = bp.get('id')
            print(f'  Found id={pid}, removing...')
            conn.cmd('/interface/bridge/port/remove', numbers=pid)
            print('  Removed')
            break

    # Add to bridge-hotspot
    result = conn.cmd('/interface/bridge/port/add', interface=iface, bridge='bridge-hotspot', comment=f'smalnets-bridge-hotspot-{iface}')
    print(f'  Add result: {result}')

    # Get the port id back for PVID
    ports2 = conn.cmd('/interface/bridge/port/print')
    for bp in ports2:
        b_iface = bp.get('interface', '')
        if b_iface == iface:
            pid2 = bp.get('id')
            print(f'  New id={pid2}, setting pvid={vlan_id}...')
            conn.cmd('/interface/bridge/port/set', numbers=pid2, pvid=str(vlan_id))
            print('  PVID set')
            break

print_bridge_ports('AFTER')

# Now remove all from bridge-hotspot and add back to default bridge
print('\n=== RESTORING default bridge ===')
ports = conn.cmd('/interface/bridge/port/print')
for bp in ports:
    iface = bp.get('interface', '')
    br = bp.get('bridge', '')
    if br == 'bridge-hotspot' and iface in ['ether3', 'ether4', 'ether5', 'wlan1']:
        pid = bp.get('id')
        print(f'  Moving {iface} back to default bridge...')
        conn.cmd('/interface/bridge/port/set', numbers=pid, bridge='bridge')
        print('  Moved')

print_bridge_ports('RESTORED')

conn.disconnect()
