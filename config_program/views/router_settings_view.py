import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from routeros.connector import RouterOSConnector
from views.styles import current_theme

logger = logging.getLogger(__name__)


class RouterSettingsDialog(QDialog):
    def __init__(self, parent, api, router_id: int, router_name: str):
        super().__init__(parent)
        self.api = api
        self.router_id = router_id
        self.router_name = router_name
        self._settings = None
        self._setup_ui()
        self.setWindowTitle(f'Router Settings — {router_name}')
        self.setMinimumSize(640, 600)
        self.setModal(True)
        QTimer.singleShot(0, self._load)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        header = QLabel(f'Router: {self.router_name}')
        header.setStyleSheet('font-size: 20px; font-weight: 700;')
        layout.addWidget(header)

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedHeight(4)
        self.loading_bar.setTextVisible(False)
        layout.addWidget(self.loading_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.settings_widget = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_widget)
        self.settings_layout.setSpacing(8)
        scroll.setWidget(self.settings_widget)
        layout.addWidget(scroll, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        host_layout = QHBoxLayout()
        host_layout.setSpacing(8)

        host_label = QLabel('Router IP / Host:')
        host_label.setStyleSheet('font-size: 12px; font-weight: 600;')
        host_layout.addWidget(host_label)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText(
            'Enter router IP address (e.g. 192.168.88.1)'
        )
        host_layout.addWidget(self.host_input, 1)

        layout.addLayout(host_layout)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(300)
        self.log_output.setObjectName('log-output')
        self.log_output.setVisible(False)
        layout.addWidget(self.log_output)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.reconfigure_btn = QPushButton('Verify && Reconfigure')
        self.reconfigure_btn.setObjectName('primary')
        self.reconfigure_btn.setCursor(Qt.PointingHandCursor)
        self.reconfigure_btn.setMinimumHeight(38)
        self.reconfigure_btn.clicked.connect(self._start_reconfigure)
        btn_layout.addWidget(self.reconfigure_btn)

        btn_layout.addStretch()

        close_btn = QPushButton('Close')
        close_btn.setMinimumHeight(38)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load(self):
        self.loading_bar.setVisible(True)
        QTimer.singleShot(50, self._do_load)

    def _do_load(self):
        try:
            self._settings = self.api.get_router_full_settings(self.router_name)
            self._populate_settings(self._settings)
        except Exception as e:
            logger.error(f'Failed to load router settings: {e}', exc_info=True)
            QMessageBox.critical(self, 'Error', f'Failed to load router settings: {e}')
        finally:
            self.loading_bar.setVisible(False)

    def _populate_settings(self, settings: dict):
        while self.settings_layout.count():
            item = self.settings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._add_section_header('Connection')
        self._add_field('API Host', settings.get('api_url', '-') or '-')
        self._add_field('API Port', str(settings.get('api_port', '-') or '-'))
        self._add_field('API User', settings.get('api_user', '-') or '-')
        self._add_field('VPN IP', settings.get('vpn_ip', '-') or '-')

        db_host = settings.get('api_url', '')
        if db_host:
            self.host_input.setText(db_host)

        self._add_section_header('Device')
        self._add_field('Serial Number', settings.get('serial_number', '-') or '-')
        self._add_field('Model', settings.get('model', '-') or '-')
        self._add_field('Firmware', settings.get('firmware_version', '-') or '-')
        self._add_field('MAC Address', settings.get('mac_address', '-') or '-')
        self._add_field('Status', settings.get('status', '-') or '-')
        self._add_field('Label', settings.get('label', '-') or '-')

        self._add_section_header('Network')
        self._add_field('WAN IP', settings.get('wan_ip', '-') or '-')
        self._add_field('LAN IP', settings.get('lan_ip', '-') or '-')
        self._add_field('LAN Subnet', settings.get('lan_subnet', '-') or '-')
        self._add_field('WiFi SSID', settings.get('wifi_ssid', '-') or '-')
        self._add_field(
            'Captive Portal URL', settings.get('captive_portal_url', '-') or '-'
        )

        self._add_section_header('WireGuard')
        self._add_field(
            'Public Key', settings.get('wg_public_key', '-') or '-', mono=True
        )
        self._add_field('GenieACS Serial', settings.get('genieacs_serial', '-') or '-')

        isp = settings.get('isp')
        if isp:
            self._add_section_header('ISP')
            self._add_field('Business Name', isp.get('business_name', '-'))
            self._add_field('Stripped Name', isp.get('stripped_name', '-'))
            self._add_field('Radius Secret', isp.get('radius_secret', '****') or '****')

        sys_info = settings.get('system_info')
        if sys_info:
            self._add_section_header('System Info (cached)')
            self._add_field('RouterOS', sys_info.get('version', '-'))
            self._add_field('Board', sys_info.get('board_name', '-'))
            self._add_field('Uptime', sys_info.get('uptime', '-'))
            self._add_field('CPU Load', f'{sys_info.get("cpu_load", "-")}%')
            self._add_field('Firmware', sys_info.get('routerboard_firmware', '-'))

        self.settings_layout.addStretch()

    def _add_section_header(self, title: str):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet('margin: 8px 0 4px 0;')
        self.settings_layout.addWidget(sep)

        label = QLabel(title)
        label.setStyleSheet('font-size: 14px; font-weight: 700; padding: 4px 0;')
        self.settings_layout.addWidget(label)

    def _add_field(self, label_text: str, value_text: str, mono: bool = False):
        row = QHBoxLayout()
        row.setSpacing(8)

        lbl = QLabel(label_text)
        lbl.setStyleSheet('font-size: 12px; font-weight: 600;')
        lbl.setFixedWidth(140)
        row.addWidget(lbl)

        val = QLabel(value_text)
        if mono:
            val.setStyleSheet('font-size: 11px; font-family: monospace;')
        else:
            val.setStyleSheet('font-size: 12px;')
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(val, 1)

        self.settings_layout.addLayout(row)

    def _log(self, msg: str):
        self.log_output.append(msg)
        # Ensure latest entry is visible
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _start_reconfigure(self):
        self.reconfigure_btn.setEnabled(False)
        self.reconfigure_btn.setText('Reconfiguring...')
        self.log_output.setVisible(True)
        self.log_output.clear()
        self._log('<b>Starting verify & reconfigure...</b>')

        host = self.host_input.text().strip()
        if not host:
            self._log(
                '<span style="color:#dc2626">✗ Host/IP address is required</span>'
            )
            self.reconfigure_btn.setEnabled(True)
            self.reconfigure_btn.setText('Verify && Reconfigure')
            return

        QTimer.singleShot(50, lambda: self._do_reconfigure(host))

    def _ok(self, msg: str):
        c = current_theme.success if current_theme else '#16a34a'
        self._log(f'<span style="color:{c}">✓ {msg}</span>')

    def _fix(self, msg: str):
        c = current_theme.warning if current_theme else '#f59e0b'
        self._log(f'<span style="color:{c}">⚡ {msg}</span>')

    def _warn(self, msg: str):
        c = current_theme.text_secondary if current_theme else '#64748b'
        self._log(f'<span style="color:{c}">⚠ {msg}</span>')

    def _err(self, msg: str):
        c = current_theme.danger if current_theme else '#dc2626'
        self._log(f'<span style="color:{c}">✗ {msg}</span>')

    def _do_reconfigure(self, host: str):
        connector = None
        try:
            self._log('<span>Fetching API credentials from server...</span>')
            creds = self.api.get_api_credentials(self.router_name)

            api_user = creds.get('username', 'admin')
            api_password = creds.get('password', '')
            api_port = creds.get('port', 8728)

            if not api_password:
                self._err('API password not found in database for this router.')
                return

            self._log(
                f'<span>Connecting to <b>{host}:{api_port}</b> as <b>{api_user}</b>...</span>'
            )

            connector = RouterOSConnector(host, api_user, api_password, api_port)

            ok, msg = connector.test_connection()
            if not ok:
                self._err(f'Socket test failed: {msg}')
                return
            self._ok(f'Socket reachable on {host}:{api_port}')

            ok, msg = connector.connect()
            if not ok:
                self._err(f'API connection failed: {msg}')
                return
            self._ok(f'API connected — {msg}')

            # --- Step 1: Identity ---
            identity = list(connector.cmd('/system/identity/print'))
            current_identity = identity[0].get('name', '') if identity else ''
            if current_identity != self.router_name:
                connector.cmd('/system/identity/set', name=self.router_name)
                self._fix(
                    f'Identity set from "{current_identity}" to "{self.router_name}"'
                )
            else:
                self._ok(f'Identity is "{current_identity}"')

            # --- Step 2: Router info ---
            resource = connector.cmd('/system/resource/print')
            board_name = resource[0].get('board-name', '') if resource else ''
            sys_version = resource[0].get('version', '') if resource else ''
            sys_uptime = resource[0].get('uptime', '') if resource else ''
            cpu_load = resource[0].get('cpu-load', '') if resource else ''
            self._log(
                f'<span>  RouterOS {sys_version} | {board_name} | Uptime: {sys_uptime} | CPU: {cpu_load}%</span>'
            )

            # --- Step 3: WireGuard interface ---
            wg_ifaces = connector.cmd('/interface/wireguard/print')
            wg0 = next((i for i in wg_ifaces if i.get('name') == 'wg0'), None)
            if wg0 is None:
                connector.cmd(
                    '/interface/wireguard/add', name='wg0', comment='smalnets-vpn'
                )
                self._fix('WireGuard interface wg0 created')
            else:
                self._ok('WireGuard interface wg0 exists')

            # --- Step 4: WireGuard IP ---
            vpn_ip = self._settings.get('vpn_ip', '')
            if vpn_ip:
                addresses = connector.cmd('/ip/address/print')
                wg_ip_found = any(
                    a.get('interface') == 'wg0'
                    and a.get('address', '').startswith(vpn_ip)
                    for a in addresses
                )
                if wg_ip_found:
                    self._ok(f'VPN IP {vpn_ip}/32 assigned to wg0')
                else:
                    connector.cmd(
                        '/ip/address/add',
                        address=f'{vpn_ip}/32',
                        interface='wg0',
                        comment='smalnets-vpn-ip',
                    )
                    self._fix(f'Added IP {vpn_ip}/32 on wg0')
            else:
                self._warn('No VPN IP configured in database')

            # --- Step 5: WireGuard peer on router (server side) ---
            peers = connector.cmd('/interface/wireguard/peers/print')
            settings_data = self.api.get_settings()
            vpn_settings = settings_data.get('vpn', {})
            server_pubkey = self.api.get_wireguard_public_key()

            existing_peer = next(
                (p for p in peers if p.get('comment') == 'smalnets-vpn-server'),
                None,
            )

            if server_pubkey and vpn_settings.get('server_address'):
                if existing_peer:
                    peer_pubkey = existing_peer.get('public-key', '')
                    if peer_pubkey == server_pubkey:
                        self._ok('WireGuard server peer is configured correctly')
                    else:
                        # Remove old peer and add new one
                        peer_id = existing_peer.get('.id', '')
                        connector.cmd(
                            '/interface/wireguard/peers/remove', numbers=peer_id
                        )
                        connector.cmd(
                            '/interface/wireguard/peers/add',
                            interface='wg0',
                            comment='smalnets-vpn-server',
                            public_key=server_pubkey,
                            allowed_address=vpn_settings.get(
                                'allowed_ips', '10.200.0.1/32'
                            ),
                            endpoint_address=vpn_settings['server_address'],
                            endpoint_port=str(vpn_settings.get('listen_port', '51820')),
                            persistent_keepalive=str(
                                vpn_settings.get('persistent_keepalive', 25)
                            ),
                        )
                        self._fix('WireGuard server peer updated with correct key')
                else:
                    connector.cmd(
                        '/interface/wireguard/peers/add',
                        interface='wg0',
                        comment='smalnets-vpn-server',
                        public_key=server_pubkey,
                        allowed_address=vpn_settings.get(
                            'allowed_ips', '10.200.0.1/32'
                        ),
                        endpoint_address=vpn_settings['server_address'],
                        endpoint_port=str(vpn_settings.get('listen_port', '51820')),
                        persistent_keepalive=str(
                            vpn_settings.get('persistent_keepalive', 25)
                        ),
                    )
                    self._fix(
                        f'WireGuard server peer added for {vpn_settings["server_address"]}'
                    )
            elif not server_pubkey:
                self._warn('Server WireGuard public key not available from server')
            else:
                self._warn('VPN server address not configured')

            # --- Step 6: Hotspot bridge ---
            bridges = connector.cmd('/interface/bridge/print')
            hs_bridge = next(
                (b for b in bridges if b.get('name') == 'bridge-hotspot'),
                None,
            )
            if hs_bridge is None:
                connector.cmd(
                    '/interface/bridge/add',
                    name='bridge-hotspot',
                    comment='smalnets-hotspot-bridge',
                )
                self._fix('bridge-hotspot was missing, created')
            else:
                self._ok('bridge-hotspot exists')

            # --- Step 7: Hotspot DHCP ---
            dhcp_servers = connector.cmd('/ip/dhcp-server/print')
            hs_dhcp = next(
                (d for d in dhcp_servers if d.get('name') == 'hotspot-dhcp'), None
            )
            if hs_dhcp:
                self._ok('hotspot-dhcp server exists')
            else:
                self._warn('hotspot-dhcp server not found')

            # --- Step 8: Hotspot profile ---
            profiles = connector.cmd('/ip/hotspot/profile/print')
            hs_profile = next((p for p in profiles if p.get('name') == 'hsprof'), None)
            if hs_profile:
                self._ok('hsprof hotspot profile exists')
            else:
                self._warn('hsprof hotspot profile not found')

            # --- Step 9: Hotspot server ---
            hs_servers = connector.cmd('/ip/hotspot/print')
            hotspot = next((s for s in hs_servers if s.get('name') == 'hotspot'), None)
            if hotspot:
                self._ok('Hotspot server is configured')
            else:
                self._warn('Hotspot server not found')

            # --- Step 10: Hotspot files ---
            try:
                captive_portal_url = self._settings.get('captive_portal_url', '') or f'{self.router_name}.portal'
                domain = settings_data.get('portal_domain', '') or self.router_name
                hotspot_files = self.api.get_hotspot_files(domain, captive_portal_url)
                existing_files = connector.cmd('/file/print')

                for f in existing_files:
                    fname = f.get('name', '')
                    if any(
                        x in fname
                        for x in [
                            'smalnets/login.html',
                            'smalnets/status.html',
                            'smalnets/alogin.html',
                        ]
                    ):
                        connector.cmd('/file/remove', numbers=fname)

                for path, content in hotspot_files.items():
                    smalnets_path = (
                        path.replace('hotspot/', 'smalnets/', 1)
                        if path.startswith('hotspot/')
                        else path
                    )
                    connector.cmd('/file/add', name=smalnets_path, contents=content)

                self._fix('Hotspot files uploaded')
            except Exception as e:
                self._err(f'Hotspot file upload failed: {e}')

            # --- Step 11: RADIUS on router ---
            isp_data = self._settings.get('isp', {})
            radius_secret = isp_data.get('radius_secret', '')
            if radius_secret and vpn_ip:
                radius_list = connector.cmd('/radius/print')
                radius_ip = '.'.join(vpn_ip.split('.')[:3]) + '.1'
                radius_configured = any(
                    r.get('address') == radius_ip for r in radius_list
                )
                if not radius_configured:
                    connector.cmd(
                        '/radius/add',
                        address=radius_ip,
                        secret=radius_secret,
                        service='hotspot',
                        comment='smalnets-radius',
                    )
                    self._fix(f'RADIUS server {radius_ip} configured')
                else:
                    self._ok('RADIUS server configured on router')
            else:
                self._warn('No RADIUS credentials available')

            # --- Step 12: Firewall NAT ---
            nat_rules = connector.cmd('/ip/firewall/nat/print')
            has_masquerade = any(
                'smalnets' in (r.get('comment', '')) and r.get('action') == 'masquerade'
                for r in nat_rules
            )
            if has_masquerade:
                self._ok('NAT masquerade exists')
            else:
                self._warn('NAT masquerade not found')

            # --- Step 12b: WiFi SSID (open, no password for hotspot) ---
            wifi_ssid = self._settings.get('wifi_ssid', '')
            if wifi_ssid:
                try:
                    from routeros.configurator import RouterOSConfigurator
                    cfg = RouterOSConfigurator(connector)
                    ok, msg = cfg.configure_wireless(wifi_ssid)
                    if ok:
                        self._fix(f'WiFi configured: {msg}')
                    else:
                        self._warn(f'WiFi: {msg}')
                except Exception as e:
                    self._warn(f'WiFi setup failed: {e}')
            else:
                self._warn('No WiFi SSID configured in database')

            connector.disconnect()
            connector = None

            self._log('<hr>')

            # --- Step 13: Server-side checks via backend ---
            self._log('<b>Running server-side checks...</b>')
            try:
                system_info = {
                    'version': sys_version,
                    'board_name': board_name,
                    'uptime': sys_uptime,
                    'cpu_load': cpu_load,
                }
                result = self.api.server_checks(
                    self.router_name,
                    system_info=system_info,
                    firmware_version=sys_version,
                )
                msg = result.get('message', '')
                report = result.get('report', {})
                fixes = result.get('fixes_applied', [])

                if fixes:
                    self._fix(f'Server: {msg} — fixes applied: {", ".join(fixes)}')
                else:
                    self._log(f'<span>{msg}</span>')

                for step_name, step_data in report.items():
                    if step_data is None:
                        continue
                    status = step_data.get('status', '')
                    step_msg = step_data.get('message', '')
                    label = step_name.replace('_', ' ').title()
                    if status == 'ok':
                        self._ok(f'{label}: {step_msg}')
                    elif status == 'fixed':
                        self._fix(f'{label}: {step_msg}')
                    elif status in ('warning', 'skipped'):
                        self._warn(f'{label}: {step_msg}')
                    else:
                        self._err(f'{label}: {step_msg}')
            except Exception as e:
                self._warn(f'Server-side checks skipped: {e}')

            self._log('<hr>')
            self._log(
                '<b style="color:%s">✓ Reconfigure complete</b>'
                % (current_theme.success if current_theme else '#16a34a')
            )

        except Exception as e:
            logger.error(f'Reconfigure failed: {e}', exc_info=True)
            self._err(f'Error: {e}')
        finally:
            import contextlib

            if connector and connector.is_connected():
                with contextlib.suppress(Exception):
                    connector.disconnect()
            self.reconfigure_btn.setEnabled(True)
            self.reconfigure_btn.setText('Verify && Reconfigure')
