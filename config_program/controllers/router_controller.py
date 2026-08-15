import logging
import secrets
import string
from urllib.parse import urlparse

from PySide6.QtCore import QObject, QTimer, Signal

from routeros.configurator import RouterOSConfigurator

logger = logging.getLogger(__name__)


class ProvisionWorker(QObject):
    step_started = Signal(str)
    step_result = Signal(str, bool, str)
    finished = Signal(object, object, object)  # config dict, router_name, router_id
    failed = Signal(str)

    def __init__(self, api, connector, parent=None):
        super().__init__(parent)
        self.api = api
        self.connector = connector

    def run(self, isp_id, isp_slug, isp_data, host, port, user, password, wifi_ssid, has_wifi):
        try:
            configurator = RouterOSConfigurator(self.connector)

            def emit(label, ok, msg):
                self.step_started.emit(label)
                self.step_result.emit(label, ok, msg)

            emit("Reading router info", False, "querying device...")
            ok, info = configurator.get_router_info()
            if not ok:
                emit("Reading router info", False, info.get('error', 'Failed'))
                return
            serial = info.get('serial_number', '')
            model = info.get('model', '')
            firmware = info.get('firmware_version', '')
            emit("Reading router info", True, f'serial={serial}, model={model}, firmware={firmware}')

            emit("Detecting interfaces for hotspots", False, "scanning...")
            ok, ifaces = configurator.get_hotspot_interfaces()
            if not ok:
                emit("Detecting interfaces", False, str(ifaces.get('error', 'Failed')))
                return
            total_ethers = sum(1 for i in ifaces if i.get('type') == 'ether') + 2
            ports_count = total_ethers
            emit("Detecting interfaces for hotspots", True, f'{len(ifaces)} hotspot interfaces found, {total_ethers} total ethernet ports')

            emit("Fetching server settings", False, "")
            settings = self.api.get_settings()
            vpn = settings.get('vpn') or {}
            genieacs = settings.get('genieacs') or {}
            emit("Fetching server settings", True, "OK")

            existing_routers = self.api.get_isp_routers(isp_slug)
            existing = next((r for r in existing_routers if r.get('serial_number') == serial), None)
            existing_names = {r.get('name', '') for r in existing_routers}
            router_name = self._compute_router_name(existing_names)
            logger.info(f'Router name: {router_name}')

            if existing and existing.get('vpn_ip'):
                vpn_ip = existing['vpn_ip']
                emit("Allocating VPN IP", True, f'reusing {vpn_ip}')
            else:
                emit("Allocating VPN IP", False, "")
                vpn_ip = self.api.get_next_vpn_ip()
                emit("Allocating VPN IP", True, f'{vpn_ip}')

            vpn_endpoint = vpn.get('server_address', '')
            if vpn.get('listen_port'):
                vpn_endpoint = f'{vpn_endpoint}:{vpn["listen_port"]}'

            server_pubkey = None
            if vpn_endpoint:
                try:
                    server_pubkey = self.api.get_wireguard_public_key()
                except Exception as e:
                    logger.warning(f'Could not fetch server public key: {e}')

            hotspot_dns_name = settings.get('hotspot_dns_name', '')
            portal_domain = settings.get('portal_domain', 'failed.smalnets.com')
            vpn_subnet = vpn.get('allowed_ips', '10.200.0.0/20')
            radius_secret = isp_data.get('radius_secret', '')
            radius_server_ip = ''
            if radius_secret:
                import ipaddress
                network = ipaddress.ip_network(vpn_subnet, strict=False)
                radius_server_ip = str(network.network_address + 1)

            parsed = urlparse(settings.get('app_url', ''))
            cp_host = parsed.hostname or ''
            parsed_port = parsed.port
            if parsed_port and parsed_port not in (80, 443):
                cp_domain = f'{cp_host}:{parsed_port}'
                portal_host = f'{portal_domain}:{parsed_port}'
                print(f"Portal domain: {portal_domain}, cp_host: {cp_host}, parsed_port: {parsed_port}, cp_domain: {cp_domain}, portal_host: {portal_host}")
            else:
                cp_domain = cp_host
                portal_host = portal_domain
                print(f"Portal domain: {portal_domain}, cp_host: {cp_host}, parsed_port: {parsed_port}, cp_domain: {cp_domain}, portal_host: {portal_host}")

            alphabet = string.ascii_letters + string.digits
            new_password = ''.join(secrets.choice(alphabet) for _ in range(16))

            emit("Saving router to server", False, "")

            api_data = {
                'isp_id': isp_id,
                'serial_number': serial,
                'model': model,
                'firmware_version': firmware,
                'ports_count': ports_count,
                'vpn_ip': vpn_ip,
                'routeros_host': host,
                'routeros_port': port,
                'routeros_user': user,
                'routeros_password': password,
                'api_password': new_password,
                'default_password': password,
                'wifi_ssid': wifi_ssid,
            }

            if existing:
                router_id = existing['id']
                router_name = existing.get('name', router_name)
                self.api.update_router(router_name, api_data)
                emit("Saving router to server", True, f'updated (name={router_name})')
            else:
                result = self.api.create_router(api_data)
                router_id = result.get('id')
                router_name = result.get('name', router_name)
                self.api.update_router(router_name, {'captive_portal_url': f'{router_name}.portal'})
                emit("Saving router to server", True, f'created (id={router_id}, name={router_name})')

            config = {
                'vpn_ip': vpn_ip,
                'vpn_endpoint': vpn_endpoint,
                'vpn_subnet': vpn_subnet,
                'vpn_listen_port': vpn.get('listen_port'),
                'vpn_keepalive': vpn.get('persistent_keepalive', 25),
                'server_pubkey': server_pubkey,
                'router_name': router_name,
                'hotspot_dns_name': hotspot_dns_name,
                'portal_domain': portal_domain,
                'radius_secret': radius_secret,
                'radius_server_ip': radius_server_ip,
                'genieacs_url': genieacs.get('acs_url', ''),
                'genieacs_username': genieacs.get('username', ''),
                'genieacs_password': genieacs.get('password', ''),
                'genieacs_interval': genieacs.get('periodic_inform_interval', 300),
                'captive_portal_server': cp_domain,
                'router_id': router_id,
                'hotspot_interfaces': ifaces,
                'routeros_host': host,
                'password_changed': True,
                'new_password': new_password,
                'old_password': password,
                'routeros_user': user,
                'wifi_ssid': wifi_ssid,
                'stripped_name': isp_data.get('stripped_name', ''),
            }

            self.finished.emit(config, router_name, router_id)
        except Exception as e:
            logger.error(f'Provision failed: {e}', exc_info=True)
            self.failed.emit(str(e))

    @staticmethod
    def _compute_router_name(existing_names: set):
        alphabet = string.ascii_letters + string.digits
        while True:
            name = ''.join(secrets.choice(alphabet) for _ in range(8))
            if name not in existing_names:
                return name


class RouterController(QObject):
    step_started = Signal(str)
    step_result = Signal(str, bool, str)
    all_done = Signal(bool, str)

    def __init__(self, api, connector):
        super().__init__()
        self.api = api
        self.connector = connector
        self.configurator = RouterOSConfigurator(connector)
        self._cancelled = False
        self._serial_number = ''
        self._router_model = ''
        self._firmware_version = ''
        self._hotspot_interfaces = []
        self._ports_count = 0

    def cancel(self):
        self._cancelled = True

    def detect_wifi(self) -> bool:
        return self.configurator.has_wireless_capability()

    def apply_configuration(self, config: dict):
        logger.info('=== Starting router configuration ===')
        self._cancelled = False
        self._config = config
        self._step_index = 0
        self._build_steps()
        QTimer.singleShot(0, self._run_next_step)

    def _build_steps(self):
        c = self._config
        configurator = self.configurator

        vpn_ip = c.get('vpn_ip', '')
        vpn_endpoint = c.get('vpn_endpoint', '')
        server_pubkey = c.get('server_pubkey', '')
        router_name = c.get('router_name', '')
        hotspot_dns_name = c.get('hotspot_dns_name', '')
        portal_domain = c.get('portal_domain', 'failed.smalnets.com')
        vpn_subnet = c.get('vpn_subnet', '10.200.0.0/20')
        radius_secret = c.get('radius_secret', '')
        radius_server_ip = c.get('radius_server_ip', '')
        genieacs_url = c.get('genieacs_url', '')
        genieacs_username = c.get('genieacs_username', '')
        genieacs_password = c.get('genieacs_password', '')
        genieacs_interval = c.get('genieacs_interval', 300)
        captive_portal_server = c.get('captive_portal_server', '')
        router_id = c.get('router_id', 0)
        stripped_name = c.get('stripped_name', '')
        hotspot_interfaces = c.get('hotspot_interfaces', [])
        wifi_ssid = c.get('wifi_ssid', '')

        self._steps = []

        self._steps.append(("Reading router info", self._do_get_router_info))
        self._steps.append(("Detecting interfaces for hotspots", self._do_detect_interfaces))
        self._steps.append(("Setting router identity", lambda: configurator.set_identity(router_name)))
        self._steps.append(("Configuring firewall rules", lambda: configurator.configure_firewall(allowed_subnets=[vpn_subnet])))

        if c.get('password_changed') and c.get('new_password'):
            old = c.get('old_password', '')
            new = c.get('new_password', '')
            user = c.get('routeros_user', 'admin')
            self._steps.append(("Changing router password", lambda u=user, o=old, n=new: configurator.change_password(u, o, n)))

        self._steps.append(("Configuring WireGuard interface + IP", lambda: configurator.configure_vpn_wireguard(
            vpn_ip, '',
            endpoint='' if vpn_endpoint else None,
            listen_port=c.get('vpn_listen_port'),
        )))

        if server_pubkey and vpn_endpoint:
            self._steps.append(("Adding WireGuard server peer", lambda: configurator.add_vpn_peer(
                server_pubkey, vpn_endpoint,
                persistent_keepalive=c.get('vpn_keepalive', 25),
            )))

        if genieacs_url and self._serial_number:
            self._steps.append(("Configuring GenieACS", lambda: configurator.configure_genieacs(
                self._serial_number,
                acs_url=genieacs_url,
                username=genieacs_username,
                password=genieacs_password,
                inform_interval=genieacs_interval,
            )))

        if radius_secret and radius_server_ip:
            self._steps.append(("Configuring RADIUS server", lambda ip=radius_server_ip, secret=radius_secret: configurator.configure_radius(ip, secret)))

        if wifi_ssid:
            self._steps.append((f"Configuring WiFi SSID: {wifi_ssid}", lambda s=wifi_ssid: configurator.configure_wireless(s)))

        self._steps.append(("Provisioning hotspot bridge", lambda: configurator.provision_hotspot_ports(
            hotspot_interfaces,
            dns_name=hotspot_dns_name,
            radius_server_ip=radius_server_ip,
            router_id=router_id,
            stripped_name=stripped_name,
            captive_portal_server=captive_portal_server,
            captive_portal_server_ip=radius_server_ip,
            portal_domain=portal_domain,
            router_name=router_name,
        )))

        self._steps.append((
            "Uploading hotspot portal",
            self._do_upload_hotspot_files
        ))

        if server_pubkey:
            self._steps.append((
                "Registering WireGuard peer on server",
                self._do_register_wireguard_peer
            ))


    def _do_register_wireguard_peer(self):
        ok, pubkey = self.configurator.get_wireguard_public_key()
        if not ok:
            return False, f"Failed to get router WireGuard public key: {pubkey}"

        vpn_ip = self._config.get('vpn_ip', '')
        if not vpn_ip:
            return False, "No VPN IP configured"

        router_host = self._config.get('routeros_host', '')
        vpn_listen_port = self._config.get('vpn_listen_port', '')
        serial_number = self._serial_number

        endpoint = ''
        if router_host and vpn_listen_port:
            endpoint = f'{router_host}:{vpn_listen_port}'

        try:
            self.api.add_wireguard_peer(
                pubkey, vpn_ip,
                endpoint=endpoint,
                persistent_keepalive=25,
                serial_number=serial_number,
            )
            logger.info(f"Registered WireGuard peer {pubkey[:20]}... for {vpn_ip} (serial={serial_number}) endpoint={endpoint}")
            return True, f"Peer {vpn_ip} registered"
        except Exception as e:
            logger.error(f"Failed to register WireGuard peer: {e}")
            return False, f"Failed to register WireGuard peer: {e}"


    def _do_upload_hotspot_files(self):
        router_name = self._config.get('router_name', '')
        logger.info(f"Fetching hotspot files for router {router_name} domain: {self._config.get('portal_domain', '')}")
        try:
            api_files = self.api.get_hotspot_files(
                domain=self._config.get('portal_domain', ''),
                captive_portal_url=f"{router_name}.portal" if router_name else 'guest.portal'
            )

            ok, result = self.configurator.upload_hotspot_files(api_files)
            if ok:
                return True, f"Uploaded {len(api_files)} hotspot files"
            else:
                return False, f"Failed to upload hotspot files: {result}"
        except Exception as e:
            logger.error(f"Failed to fetch or upload hotspot files: {e}", exc_info=True)
            return False, f"Failed to fetch or upload hotspot files: {e}"


    def _run_next_step(self):
        if self._cancelled:
            self.all_done.emit(False, "Cancelled by user")
            return
        if self._step_index >= len(self._steps):
            self.all_done.emit(True, "All steps completed")
            return
        label, func = self._steps[self._step_index]
        self.step_started.emit(label)
        try:
            ok, msg = func()
            self.step_result.emit(label, ok, msg)
            if not ok:
                self.all_done.emit(False, f"{label}: {msg}")
                return
            self._step_index += 1
            QTimer.singleShot(0, self._run_next_step)
        except Exception as e:
            logger.error(f'Step failed: {label}: {e}', exc_info=True)
            self.step_result.emit(label, False, str(e))
            self.all_done.emit(False, f"{label}: {e}")

    def _do_get_router_info(self) -> tuple[bool, str]:
        ok, info = self.configurator.get_router_info()
        if ok:
            self._serial_number = info.get('serial_number', '')
            self._router_model = info.get('model', '')
            self._firmware_version = info.get('firmware_version', '')
            return True, f'serial={self._serial_number}, model={self._router_model}, firmware={self._firmware_version}'
        return False, str(info.get('error', 'Failed'))

    def _do_detect_interfaces(self) -> tuple[bool, str]:
        ok, ifaces = self.configurator.get_hotspot_interfaces()
        if ok:
            self._hotspot_interfaces = ifaces
            total_ethers = sum(1 for i in ifaces if i.get('type') == 'ether') + 2
            self._ports_count = total_ethers
            self._config['hotspot_interfaces'] = ifaces
            return True, f'{len(ifaces)} hotspot interfaces found, {total_ethers} total ethernet ports'
        return False, str(ifaces.get('error', 'Failed'))

    @property
    def serial_number(self):
        return self._serial_number

    @property
    def router_model(self):
        return self._router_model

    @property
    def firmware_version(self):
        return self._firmware_version

    @property
    def ports_count(self):
        return self._ports_count
