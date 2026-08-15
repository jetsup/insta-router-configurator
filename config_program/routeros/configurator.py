import contextlib
import logging

from .connector import RouterOSConnector

logger = logging.getLogger(__name__)


class RouterOSConfigurator:
    def __init__(self, connector: RouterOSConnector):
        self.conn = connector

    def set_identity(self, name: str) -> tuple[bool, str]:
        try:
            self.conn.cmd('/system/identity/set', name=name)
            return True, f'Router name set to {name}'
        except Exception as e:
            return False, str(e)

    def get_router_info(self) -> tuple[bool, dict]:
        try:
            board = self.conn.cmd('/system/routerboard/print')
            resource = self.conn.cmd('/system/resource/print')
            if not board:
                return False, {}
            info = board[0]
            serial = info.get('serial-number', '')
            model = info.get('model', '')
            raw_version = resource[0].get('version', '') if resource else ''
            version = raw_version.split(' ')[0] if raw_version else info.get('current-firmware', '')
            if not serial:
                return False, {}
            return True, {
                'serial_number': serial,
                'model': model,
                'firmware_version': version,
            }
        except Exception as e:
            return False, {'error': str(e)}

    def get_hotspot_interfaces(self) -> tuple[bool, list]:
        try:
            ifaces = self.conn.cmd('/interface/print')
            ethers = [i for i in ifaces if i.get('type') == 'ether' and i.get('name') not in ('ether1', 'ether2')]
            wlans = [i for i in ifaces if i.get('type') in ('wlan', 'wifi', 'wireless')]
            all_ifaces = ethers + wlans
            if not all_ifaces:
                return True, []
            return True, [
                {
                    'name': i.get('name', ''),
                    'type': i.get('type', ''),
                    'mac_address': i.get('mac-address', ''),
                    'running': i.get('running', 'false') == 'true',
                }
                for i in all_ifaces
            ]
        except Exception as e:
            return False, {'error': str(e)}

    def change_password(self, username: str, old_password: str, new_password: str) -> tuple[bool, str]:
        if new_password == old_password or not new_password:
            return True, 'Password unchanged (same as current)'
        try:
            users = self.conn.cmd('/user/print')
            user = next((u for u in users if u.get('name') == username), None)
            if user is None:
                return False, f'User {username} not found'
            self.conn.cmd('/user/set', numbers=user.get('id'), password=new_password)
            return True, 'Password changed successfully'
        except Exception as e:
            return False, str(e)

    def configure_wan(self, wan_ip: str | None = None, wan_gateway: str | None = None) -> tuple[bool, str]:
        try:
            if wan_ip and '/' in wan_ip:
                self.conn.cmd('/ip/address/add', address=wan_ip, interface='ether1', comment='smalnets-wan')
            if wan_gateway:
                self.conn.cmd('/ip/route/add', dst_address='0.0.0.0/0', gateway=wan_gateway, comment='smalnets-wan-gw')
            return True, 'WAN configured'
        except Exception as e:
            msg = str(e)
            if 'already have such address' in msg.lower():
                return True, 'WAN IP already assigned (resumed)'
            return False, msg

    def configure_lan(self, lan_ip: str, lan_subnet: str) -> tuple[bool, str]:
        try:
            interface = 'bridge' if self._interface_exists('bridge') else 'ether2'
            self.conn.cmd('/ip/address/add', address=f'{lan_ip}/{lan_subnet.split("/")[1] if "/" in lan_subnet else "24"}', interface=interface, comment='smalnets-lan')
            return True, f'LAN configured on {interface}'
        except Exception as e:
            msg = str(e)
            if 'already have such address' in msg.lower():
                return True, 'LAN IP already assigned (resumed)'
            return False, msg

    def configure_vpn_wireguard(self, vpn_ip: str, vpn_gateway: str, private_key: str | None = None, endpoint: str | None = None, listen_port: str | None = None) -> tuple[bool, str]:
        try:
            existing = self.conn.cmd('/interface/wireguard/print')
            wg_interface = None
            for iface in existing:
                if iface.get('name') == 'wg0':
                    wg_interface = iface
                    break

            if not wg_interface:
                result = self.conn.cmd('/interface/wireguard/add', name='wg0', comment='smalnets-vpn')
                wg_interface = result[0] if result else {'name': 'wg0'}

            if private_key:
                self.conn.cmd('/interface/wireguard/set', numbers=wg_interface.get('.id', 'wg0'), private_key=private_key)

            if listen_port:
                current_port = wg_interface.get('listen-port', '')
                if current_port != listen_port:
                    self.conn.cmd('/interface/wireguard/set', numbers=wg_interface.get('.id', 'wg0'), **{'listen-port': listen_port})

            self.conn.cmd('/ip/address/add', address=f'{vpn_ip}/32', interface='wg0', comment='smalnets-vpn-ip')

            if endpoint and vpn_gateway:
                self.conn.cmd('/ip/route/add', dst_address=f'{vpn_gateway}/32', gateway='wg0', comment='smalnets-vpn-route')

            # Route for VPS WireGuard IP so pings work without forcing interface
            self.conn.cmd('/ip/route/add', dst_address='10.200.0.1/32', gateway='wg0', comment='WireGuard VPS')

            return True, f'WireGuard VPN configured with IP {vpn_ip}'
        except Exception as e:
            msg = str(e)
            if 'already have such address' in msg.lower():
                return True, f'IP {vpn_ip} already assigned (resumed)'
            if 'already have' in msg.lower() and '10.200.0.1/32' in msg:
                return True, 'Route to VPS already exists (resumed)'
            return False, msg

    def configure_dhcp_server(self, lan_subnet: str, dns_servers: str = '8.8.8.8,8.8.4.4') -> tuple[bool, str]:
        try:
            interface = 'bridge' if self._interface_exists('bridge') else 'ether2'
            pool_name = 'smalnets-dhcp'
            network_part = lan_subnet.rsplit('.', 1)[0] if '/' not in lan_subnet else lan_subnet.rsplit('/', 1)[0].rsplit('.', 1)[0]
            gateway = f'{network_part}.1'
            start = f'{network_part}.10'
            end = f'{network_part}.200'

            self.conn.cmd('/ip/dhcp-server/network/add', address=lan_subnet, gateway=gateway, dns_server=dns_servers, comment='smalnets-dhcp-net')
            self.conn.cmd('/ip/pool/add', name=pool_name, ranges=f'{start}-{end}', comment='smalnets-dhcp-pool')
            self.conn.cmd('/ip/dhcp-server/add', name='smalnets-dhcp', interface=interface, address_pool=pool_name, lease_time='10m', comment='smalnets-dhcp')

            return True, f'DHCP server configured ({start} – {end})'
        except Exception as e:
            return False, str(e)

    def configure_hotspot(self, lan_subnet: str, captive_portal_url: str, dns_name: str | None = None) -> tuple[bool, str]:
        try:
            interface = 'bridge' if self._interface_exists('bridge') else 'ether2'
            network_part = lan_subnet.rsplit('.', 1)[0] if '/' not in lan_subnet else lan_subnet.rsplit('/', 1)[0].rsplit('.', 1)[0]

            self.conn.cmd('/ip/hotspot/set', interface=interface, address_pool='smalnets-dhcp', enabled='yes')
            self.conn.cmd('/ip/hotspot/profile/set', numbers=0, hotspot_address=f'{network_part}.1', dns_name=dns_name or '')

            wlan = self._get_wlan_interface()
            if wlan:
                self.conn.cmd('/ip/hotspot/set', interface=wlan, enabled='yes')

            self.conn.cmd('/ip/firewall/nat/add', chain='srcnat', action='masquerade', comment='smalnets-masq')
            self.conn.cmd('/ip/firewall/nat/add', chain='dstnat', protocol='tcp', dst_port='80', action='redirect', to_ports='64800', comment='smalnets-captive')

            return True, 'Hotspot configured'
        except Exception as e:
            return False, str(e)

    BRIDGE_NAME = 'bridge-hotspot'

    CAPTIVE_PORTAL_DOMAINS = [
        'http://connectivitycheck.android.com/generate_204',
        'http://play.googleapis.com/generate_204',
        'http://connectivitycheck.gstatic.com',
        'http://clients3.google.com',
        'http://captive.apple.com',
        'http://www.msftconnecttest.com',
        'http://msftconnecttest.com',
        'http://detectportal.firefox.com',
    ]

    @staticmethod
    def _remove_by_comment_prefix(conn, paths: list[str], prefix: str) -> None:
        for path in paths:
            try:
                items = conn.cmd(path)
                remove_path = path.removesuffix('/print') + '/remove'
                ids = [
                    item.get('.id', '') or item.get('id', '')
                    for item in items
                    if item.get('comment', '').startswith(prefix)
                ]
                for item_id in ids:
                    if item_id:
                        with contextlib.suppress(Exception):
                            conn.cmd(remove_path, numbers=item_id)
            except Exception:
                pass

    def _add_captive_portal_detection(self, gateway: str, hs_name: str, comment_prefix: str) -> None:
        for domain in self.CAPTIVE_PORTAL_DOMAINS:
            # Extract a short unique label from the domain
            label = domain.replace('http://', '').replace('https://', '').split('/')[0].replace('.', '-').replace('www.', '')[:24]
            with contextlib.suppress(Exception):
                self.conn.cmd('/ip/hotspot/walled-garden/add', action='allow', dst_host=domain, server=hs_name, comment=f'{comment_prefix}-cp-{label}')
            with contextlib.suppress(Exception):
                self.conn.cmd('/ip/dns/static/add', name=domain, address=gateway, ttl='5m', comment=f'{comment_prefix}-dns-{label}')

    @staticmethod
    def _resolve_port_interface(bp: dict) -> str:
        iface = bp.get('interface')
        if isinstance(iface, dict):
            return iface.get('name', '')
        return str(iface) if iface is not None else ''

    @staticmethod
    def _is_duplicate_error(e: Exception) -> bool:
        msg = str(e).lower()
        return any(p in msg for p in [
            'already exist',
            'already have',
            'already added',
            'such name exists',
        ])

    def _remove_interface_from_bridge(self, interface: str) -> None:
        ports = self.conn.cmd('/interface/bridge/port/print')
        for bp in ports:
            if self._resolve_port_interface(bp) == interface:
                with contextlib.suppress(Exception):
                    self.conn.cmd('/interface/bridge/port/remove', numbers=bp.get('id'))
                break

    def _add_interface_to_bridge(self, interface: str, bridge: str) -> None:
        self._remove_interface_from_bridge(interface)
        self.conn.cmd('/interface/bridge/port/add', interface=interface, bridge=bridge, horizon='none', comment=f'smalnets-{bridge}-port')

    def provision_hotspot_ports(self, interfaces: list[dict], dns_name: str = '', radius_server_ip: str = '', router_id: int = 0, stripped_name: str = '', captive_portal_server: str = '', captive_portal_server_ip: str = '', portal_domain: str = '', router_name: str = '') -> tuple[bool, dict]:
        try:
            if dns_name or (router_id and stripped_name):
                if router_id and stripped_name:
                    resolved_dns = f'hs.h{router_id}.{stripped_name}.com'
                else:
                    resolved_dns = dns_name
            else:
                resolved_dns = ''

            try:
                self.conn.cmd('/interface/bridge/add', name=self.BRIDGE_NAME, comment='smalnets-hotspot-bridge')
            except Exception as e:
                if not self._is_duplicate_error(e):
                    return False, {'error': str(e)}

            for iface_config in interfaces:
                self._add_interface_to_bridge(iface_config['name'], self.BRIDGE_NAME)

            try:
                self.conn.cmd('/ip/address/add', address='192.168.10.1/24', interface=self.BRIDGE_NAME, comment='smalnets-hotspot-gw')
            except Exception as e:
                if not self._is_duplicate_error(e):
                    return False, {'error': str(e)}

            try:
                self.conn.cmd('/ip/pool/add', name='hs-pool', ranges='192.168.10.10-192.168.10.254', comment='smalnets-hotspot-pool')
            except Exception as e:
                if not self._is_duplicate_error(e):
                    return False, {'error': str(e)}

            try:
                self.conn.cmd('/ip/dhcp-server/network/add', address='192.168.10.0/24', gateway='192.168.10.1', dns_server='192.168.10.1', comment='smalnets-hotspot-dhcp-net')
            except Exception as e:
                if not self._is_duplicate_error(e):
                    return False, {'error': str(e)}
                with contextlib.suppress(Exception):
                    self.conn.cmd('/ip/dhcp-server/network/set', address='192.168.10.0/24', gateway='192.168.10.1', dns_server='192.168.10.1')

            try:
                self.conn.cmd('/ip/dhcp-server/add', name='hotspot-dhcp', interface=self.BRIDGE_NAME, address_pool='hs-pool', lease_time='10m', comment='smalnets-hotspot-dhcp')
            except Exception as e:
                if not self._is_duplicate_error(e):
                    return False, {'error': str(e)}
                self.conn.cmd('/ip/dhcp-server/set', numbers='hotspot-dhcp', interface=self.BRIDGE_NAME, address_pool='hs-pool', lease_time='10m')

            existing_profiles = self.conn.cmd('/ip/hotspot/profile/print')
            if any(p.get('name') == 'hsprof' for p in existing_profiles):
                self.conn.cmd('/ip/hotspot/profile/set', numbers='hsprof', hotspot_address='192.168.10.1', dns_name=resolved_dns, use_radius='yes', radius_accounting='yes', html_directory='smalnets', **{'login-by': 'http-pap,http-chap,cookie'})
            else:
                self.conn.cmd('/ip/hotspot/profile/add', name='hsprof', hotspot_address='192.168.10.1', dns_name=resolved_dns, use_radius='yes', radius_accounting='yes', html_directory='smalnets', **{'login-by': 'http-pap,http-chap,cookie'})

            try:
                self.conn.cmd('/ip/hotspot/add', interface=self.BRIDGE_NAME, address_pool='hs-pool', name='hotspot', disabled='no', profile='hsprof')
            except Exception as e:
                if not self._is_duplicate_error(e):
                    return False, {'error': str(e)}
                self.conn.cmd('/ip/hotspot/set', numbers='hotspot', interface=self.BRIDGE_NAME, address_pool='hs-pool', disabled='no', profile='hsprof')

            # Clean up smalnets entries for idempotency before re-adding
            self._remove_by_comment_prefix(
                self.conn,
                [
                    '/ip/hotspot/walled-garden/print',
                    '/ip/hotspot/walled-garden/ip/print',
                    '/ip/dns/static/print',
                    '/ip/firewall/nat/print',
                ],
                'smalnets',
            )

            try:
                self.conn.cmd('/ip/firewall/nat/add', chain='srcnat', action='masquerade', comment='smalnets-hotspot-masq')
            except Exception as e:
                if not self._is_duplicate_error(e):
                    return False, {'error': str(e)}

            if radius_server_ip:
                try:
                    self.conn.cmd('/ip/hotspot/walled-garden/ip/add', action='accept', dst_address=radius_server_ip, dst_port='443', protocol='tcp', comment='smalnets-radius443')
                except Exception as e:
                    if not self._is_duplicate_error(e):
                        return False, {'error': str(e)}
                try:
                    self.conn.cmd('/ip/hotspot/walled-garden/ip/add', action='accept', dst_address=radius_server_ip, comment='smalnets-radius')
                except Exception as e:
                    if not self._is_duplicate_error(e):
                        return False, {'error': str(e)}
                try:
                    self.conn.cmd('/ip/hotspot/walled-garden/add', action='allow', dst_host=radius_server_ip, server='hotspot', comment='smalnets-radius-dns')
                except Exception as e:
                    if not self._is_duplicate_error(e):
                        return False, {'error': str(e)}

            if resolved_dns:
                try:
                    self.conn.cmd('/ip/hotspot/walled-garden/add', action='allow', dst_host=resolved_dns, server='hotspot', comment='smalnets-portal')
                except Exception as e:
                    if not self._is_duplicate_error(e):
                        return False, {'error': str(e)}
                try:
                    self.conn.cmd('/ip/dns/static/add', name=resolved_dns, address='192.168.10.1', ttl='5m', comment='smalnets-dns')
                except Exception as e:
                    if not self._is_duplicate_error(e):
                        return False, {'error': str(e)}

            if captive_portal_server:
                import socket

                parts = captive_portal_server.rsplit(':', 1)
                cp_host = parts[0]

                # DNS-based walled garden entry — does not need an IP
                try:
                    self.conn.cmd(
                        '/ip/hotspot/walled-garden/add',
                        action='allow',
                        dst_host=cp_host,
                        server='hotspot',
                        comment='smalnets-cp-host'
                    )
                except Exception as e:
                    if not self._is_duplicate_error(e):
                        return False, {'error': str(e)}

                if captive_portal_server_ip:
                    try:
                        cp_host_ip = socket.gethostbyname(cp_host)
                        print(f"Resolved {cp_host} to {cp_host_ip}")
                    except socket.gaierror:
                        return False, {
                            "error": f"Unable to resolve {cp_host}"
                        }

                    cp_port = parts[1] if len(parts) > 1 else "443"

                    try:
                        self.conn.cmd('/ip/hotspot/walled-garden/ip/add', action='accept', dst_address=cp_host_ip, dst_port=cp_port, protocol='tcp', server='hotspot', comment='smalnets-cp-server')
                    except Exception as e:
                        if not self._is_duplicate_error(e):
                            return False, {'error': str(e)}

                    if portal_domain:
                        # DNS entry so hotspot clients resolve portal_domain -> server IP
                        try:
                            self.conn.cmd('/ip/dns/static/add', name=portal_domain, address=cp_host_ip, ttl='5m', comment='smalnets-portal-dns')
                        except Exception as e:
                            if not self._is_duplicate_error(e):
                                return False, {'error': str(e)}
                        # Walled garden entry so DNS query passes through
                        try:
                            self.conn.cmd('/ip/hotspot/walled-garden/add', action='allow', dst_host=portal_domain, server='hotspot', comment='smalnets-portal-domain')
                        except Exception as e:
                            if not self._is_duplicate_error(e):
                                return False, {'error': str(e)}

                    # Vite dev server port for asset loading during development
                    try:
                        self.conn.cmd('/ip/hotspot/walled-garden/ip/add', action='accept', dst_address=cp_host_ip, dst_port='5173', protocol='tcp', server='hotspot', comment='smalnets-vite')
                    except Exception as e:
                        if not self._is_duplicate_error(e):
                            return False, {'error': str(e)}

            self._add_captive_portal_detection('192.168.10.1', 'hotspot', 'smalnets')

            captive_portal_url = f'{router_name}.portal' if router_name else 'guest.portal'

            # Do the file download and upload from here


            return True, {
                'interface': self.BRIDGE_NAME,
                'bridge': self.BRIDGE_NAME,
                'name': 'hotspot',
                'captive_portal_url': captive_portal_url,
                'ip_range': '192.168.10.10-192.168.10.254',
                'gateway': '192.168.10.1',
                'subnet': '192.168.10.0/24',
            }
        except Exception as e:
            return False, {'error': str(e)}

    def configure_firewall(self, allowed_subnets: list | None = None) -> tuple[bool, str]:
        try:
            existing = self.conn.cmd('/ip/firewall/filter/print')
            has_defconf = any('defconf' in r.get('comment', '') for r in existing)
            added = 0

            if allowed_subnets:
                drop_pos = None
                for i, r in enumerate(existing):
                    if (r.get('chain') == 'input' and r.get('action') == 'drop'
                            and r.get('in-interface-list') == '!LAN'
                            and 'defconf' in r.get('comment', '')):
                        drop_pos = i
                        break

                for subnet in allowed_subnets:
                    kwargs = {'src_address': subnet, 'comment': 'smalnets-allow-subnet'}
                    if not has_defconf:
                        kwargs['chain'] = 'input'
                        kwargs['action'] = 'accept'
                        self.conn.cmd('/ip/firewall/filter/add', **kwargs)
                    elif drop_pos is not None:
                        self.conn.cmd('/ip/firewall/filter/add', chain='input', action='accept', **{'place-before': str(drop_pos)}, **kwargs)
                    else:
                        self.conn.cmd('/ip/firewall/filter/add', chain='input', action='accept', **kwargs)
                    added += 1

            if not has_defconf:
                extra = [
                    ('input', 'accept', {'protocol': 'icmp', 'comment': 'smalnets-allow-icmp'}),
                    ('input', 'accept', {'connection_state': 'established,related', 'comment': 'smalnets-allow-est'}),
                    ('input', 'accept', {'protocol': 'tcp', 'dst_port': '8291', 'comment': 'smalnets-winbox'}),
                    ('input', 'accept', {'protocol': 'tcp', 'dst_port': '22', 'comment': 'smalnets-ssh'}),
                    ('input', 'accept', {'protocol': 'tcp', 'dst_port': '8728-8729', 'comment': 'smalnets-api'}),
                    ('input', 'drop', {'comment': 'smalnets-drop-other'}),
                ]
                for chain, action, attrs in extra:
                    self.conn.cmd('/ip/firewall/filter/add', chain=chain, action=action, **attrs)
                    added += 1

            return True, f'Applied {added} firewall rule(s)'
        except Exception as e:
            return False, str(e)

    def add_vpn_peer(self, server_pubkey: str, endpoint: str, allowed_ips: str = '10.200.0.1/32', persistent_keepalive: int = 25) -> tuple[bool, str]:
        try:
            existing = self.conn.cmd('/interface/wireguard/peers/print')
            for peer in existing:
                if peer.get('public-key') == server_pubkey:
                    return True, 'Server peer already exists'

            ep_addr = endpoint
            ep_port = None
            if ':' in endpoint:
                ep_addr, ep_port = endpoint.rsplit(':', 1)

            self.conn.cmd('/interface/wireguard/peers/add',
                interface='wg0',
                comment='smalnets-vpn-server',
                public_key=server_pubkey,
                allowed_address=allowed_ips,
                persistent_keepalive=str(persistent_keepalive),
                endpoint_address=ep_addr if ep_addr else None,
                endpoint_port=ep_port if ep_port else None,
            )
            return True, f'Server peer added: {endpoint}'
        except Exception as e:
            return False, str(e)

    def configure_genieacs(self, serial: str, acs_url: str = '', username: str = '', password: str = '', inform_interval: int = 300) -> tuple[bool, str]:
        try:
            self.conn.cmd('/system/device-mode/print')
            params = {}
            if acs_url:
                params['acs-url'] = acs_url
            if username:
                params['acs-user'] = username
            if password:
                params['acs-pass'] = password
            if inform_interval:
                params['periodic-inform'] = str(inform_interval)
            if params:
                params['comment'] = 'smalnets-genieacs'
                self.conn.cmd('/system/device-mode/set', **params)

            self.conn.cmd('/system/identity/set', name=f'{serial}')
            return True, f'GenieACS configured with serial {serial}'
        except Exception as e:
            return False, str(e)

    def configure_radius(self, server_ip: str, secret: str) -> tuple[bool, str]:
        try:
            radius_list = self.conn.cmd('/radius/print')
            existing = any(r.get('address') == server_ip for r in radius_list)
            if not existing:
                self.conn.cmd('/radius/add', address=server_ip, secret=secret, service='hotspot', comment='smalnets-radius')
            else:
                self.conn.cmd('/radius/set', numbers=[r.get('id') for r in radius_list if r.get('address') == server_ip][0], secret=secret, service='hotspot')
            return True, f'RADIUS server {server_ip} configured'
        except Exception as e:
            return False, f'RADIUS configuration failed: {e}'

    def _interface_exists(self, name: str) -> bool:
        try:
            result = self.conn.cmd('/interface/print', name=name)
            return len(result) > 0
        except Exception:
            return False

    def _get_wlan_interface(self) -> str | None:
        try:
            interfaces = self.conn.cmd('/interface/wireless/print')
            for iface in interfaces:
                name = iface.get('name', '')
                if name.startswith('wlan') or name.startswith('wl'):
                    return name
        except Exception:
            pass
        return None

    def has_wireless_capability(self) -> bool:
        return self._get_wlan_interface() is not None

    def configure_wireless(self, ssid: str) -> tuple[bool, str]:
        try:
            wlan = self._get_wlan_interface()
            if not wlan:
                return False, 'No wireless interface found'
            # Ensure open security profile (no password) for hotspot
            existing_profiles = self.conn.cmd('/interface/wireless/security-profiles/print')
            open_profile = next((p for p in existing_profiles if p.get('name') == 'smalnets-open'), None)
            if open_profile is None:
                self.conn.cmd('/interface/wireless/security-profiles/add', name='smalnets-open', mode='none')
            else:
                self.conn.cmd('/interface/wireless/security-profiles/set', numbers='smalnets-open', mode='none')
            self.conn.cmd('/interface/wireless/set', numbers=wlan, ssid=ssid, mode='ap-bridge',
                          security_profile='smalnets-open', disabled='no')
            self.conn.cmd('/interface/set', numbers=wlan, disabled='no')
            return True, f'WiFi configured with SSID "{ssid}" (open, no password) on {wlan}'
        except Exception as e:
            return False, str(e)

    def get_wireguard_public_key(self) -> tuple[bool, str]:
        try:
            interfaces = self.conn.cmd('/interface/wireguard/print')
            for iface in interfaces:
                if iface.get('name') == 'wg0':
                    pubkey = iface.get('public-key', '')
                    if pubkey:
                        return True, pubkey
            return False, 'wg0 not found or has no public key'
        except Exception as e:
            return False, str(e)

    def _detect_hotspot_dir(self, existing: list[dict]) -> str:
        """Detect whether router uses flash/ prefix for hotspot files.

        Some models (L009, RouterOS 7+) mount flash at /flash/ so hotspot
        files live at flash/smalnets/.  Others (RB951, older devices) mount
        flash at root so files live at smalnets/.
        """
        for f in existing:
            name: str = f.get('name', '')
            if name == 'flash' or name.startswith('flash/'):
                return 'flash/smalnets/'
        return 'smalnets/'

    def upload_hotspot_files(self, files: dict[str, str]) -> tuple[bool, str]:
        try:
            existing = self.conn.cmd('/file/print')
            hotspot_dir = self._detect_hotspot_dir(existing)

            # Remove existing hotspot HTML files to avoid "file already exists"
            for f in existing:
                fname: str = f.get('name', '')
                if fname.endswith('smalnets/login.html') or fname.endswith('smalnets/status.html') or fname.endswith('smalnets/alogin.html'):
                    with contextlib.suppress(Exception):
                        self.conn.cmd('/file/remove', numbers=fname)

            for path, content in files.items():
                smalnets_path = path.replace('hotspot/', hotspot_dir, 1) if path.startswith('hotspot/') else path
                self.conn.cmd('/file/add', name=smalnets_path, contents=content)
            return True, 'Hotspot files uploaded to router'
        except Exception as e:
            return False, f'Hotspot file upload failed: {e}'
