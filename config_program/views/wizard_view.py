import contextlib
import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from controllers.router_controller import ProvisionWorker, RouterController
from routeros.connector import RouterOSConnector
from views.styles import current_theme

logger = logging.getLogger(__name__)

STEP_ICONS = ["①", "②"]
STEP_TITLES = ["Connect to Router", "Configure"]
STEP_DESCS = [
    "Establish connection to the MikroTik router",
    "Review and apply configuration",
]


class StepIndicator(QWidget):
    def __init__(self, step_index, icon, title, desc, active=False, done=False):
        super().__init__()
        self._active = active
        self._done = done
        self.step_index = step_index
        self.setObjectName("step-indicator")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        self.dot = QLabel(icon)
        self.dot.setFixedSize(32, 32)
        self.dot.setAlignment(Qt.AlignCenter)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet("font-size: 13px; font-weight: 700;")
        texts.addWidget(self._title_label)
        self._desc_label = QLabel(desc)
        self._desc_label.setStyleSheet("font-size: 11px;")
        texts.addWidget(self._desc_label)

        layout.addWidget(self.dot)
        layout.addLayout(texts, 1)

        self._update_style()

    def _update_style(self):
        if self._done:
            self.dot.setObjectName("step-dot-done")
            self._title_label.setObjectName("step-title-done")
            self._desc_label.setObjectName("step-desc-done")
        elif self._active:
            self.dot.setObjectName("step-dot-active")
            self._title_label.setObjectName("step-title-active")
            self._desc_label.setObjectName("step-desc-active")
        else:
            self.dot.setObjectName("step-dot")
            self._title_label.setObjectName("step-title")
            self._desc_label.setObjectName("step-desc")
        for w in (self.dot, self._title_label, self._desc_label):
            w.style().unpolish(w)
            w.style().polish(w)

    def set_active(self, active):
        self._active = active
        self._update_style()

    def set_done(self, done):
        self._done = done
        self._update_style()


class ConnectionStep(QWidget):
    connection_tested = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(self._labeled("RouterOS Host / IP"))
        self.host_input = QLineEdit("192.168.88.1")
        layout.addWidget(self.host_input)

        layout.addWidget(self._labeled("Port"))
        self.port_input = QLineEdit("8728")
        self.port_input.setMaximumWidth(120)
        layout.addWidget(self.port_input)

        layout.addWidget(self._labeled("Username"))
        self.user_input = QLineEdit("admin")
        layout.addWidget(self.user_input)

        layout.addWidget(self._labeled("Password"))
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.pass_input)

        layout.addSpacing(4)

        self.status_label = QLabel("")
        self.status_label.setFixedHeight(24)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _labeled(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-size: 12px; font-weight: 600;")
        return label

    def trigger_test(self):
        host = self.host_input.text().strip()
        port_str = self.port_input.text().strip()
        user = self.user_input.text().strip()
        pw = self.pass_input.text()

        if not host or not user:
            self.status_label.setText("Host and username required")
            self.status_label.setStyleSheet(f"color: {(current_theme.danger if current_theme else '#dc2626')}; font-size: 12px;")
            return

        try:
            port = int(port_str) if port_str else 8728
        except ValueError:
            self.status_label.setText("Port must be a number")
            self.status_label.setStyleSheet(f"color: {(current_theme.danger if current_theme else '#dc2626')}; font-size: 12px;")
            return

        self.status_label.setText("Testing...")
        self.status_label.setStyleSheet("font-size: 12px; font-style: italic;")
        self._test_async(host, port, user, pw)

    def _test_async(self, host, port, user, pw):
        conn = RouterOSConnector(host, user, pw, port)
        ok, msg = conn.test_connection()
        connected = False
        if ok:
            ok2, msg2 = conn.connect()
            if ok2:
                self._connector = conn
                self._host = host
                self._port = port
                self._user = user
                self._pw = pw
                self.status_label.setText(f"✓ {msg2}")
                self.status_label.setStyleSheet(f"color: {(current_theme.success if current_theme else '#16a34a')}; font-size: 12px; font-weight: 600;")
                connected = True
            else:
                self.status_label.setText(f"✗ {msg2}")
                self.status_label.setStyleSheet(f"color: {(current_theme.danger if current_theme else '#dc2626')}; font-size: 12px;")
        else:
            self.status_label.setText(f"✗ {msg}")
            self.status_label.setStyleSheet(f"color: {(current_theme.danger if current_theme else '#dc2626')}; font-size: 12px;")
        self.connection_tested.emit(connected, "")

    @property
    def connector(self):
        return getattr(self, '_connector', None)

    @property
    def host(self):
        return getattr(self, '_host', '')

    @property
    def port(self):
        return getattr(self, '_port', 8728)

    @property
    def user(self):
        return getattr(self, '_user', '')

    @property
    def password(self):
        return getattr(self, '_pw', '')

    @property
    def is_connected(self):
        return self.connector is not None and self.connector.is_connected()





class ConfigStep(QWidget):
    def __init__(self, has_wifi=False, isp_name="", router_model="", default_ssid=""):
        super().__init__()
        self._has_wifi = has_wifi
        self._isp_name = isp_name
        self._router_model = router_model
        self._default_ssid = default_ssid
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("Configuration Summary")
        header.setStyleSheet("font-size: 16px; font-weight: 700; padding-bottom: 4px;")
        layout.addWidget(header)

        items = [
            ("VPN", "WireGuard tunnel to central server"),
            ("GenieACS", "CPE auto-configuration with TR-069"),
            ("RADIUS", "NAS registration for authentication"),
            ("Hotspot", "Single bridge with captive portal"),
        ]
        for title, desc in items:
            row = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet("font-size: 8px;")
            row.addWidget(dot)
            t = QLabel(title)
            t.setStyleSheet("font-size: 13px; font-weight: 600;")
            row.addWidget(t)
            d = QLabel(desc)
            d.setStyleSheet("font-size: 12px;")
            row.addWidget(d, 1)
            layout.addLayout(row)

        if self._has_wifi:
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setFixedHeight(1)
            sep.setObjectName("separator")
            sep.setStyleSheet("margin: 8px 0;")
            layout.addWidget(sep)

            wifi_header = QLabel("WiFi")
            wifi_header.setStyleSheet("font-size: 14px; font-weight: 700;")
            layout.addWidget(wifi_header)

            layout.addWidget(self._labeled("WiFi Network Name (SSID)"))
            self.ssid_input = QLineEdit()
            self.ssid_input.setText(self._default_ssid)
            layout.addWidget(self.ssid_input)

            note = QLabel("Open network — hotspot handles authentication")
            note.setStyleSheet("font-size: 11px; font-style: italic;")
            layout.addWidget(note)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFixedHeight(1)
        sep2.setObjectName("separator")
        sep2.setStyleSheet("margin: 8px 0;")
        layout.addWidget(sep2)

        info = QLabel("Click 'Apply & Save' to provision the router with these settings")
        info.setStyleSheet("font-size: 12px;")
        layout.addWidget(info)

        layout.addStretch()

    def _labeled(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-size: 12px; font-weight: 600;")
        return label

    @property
    def wifi_ssid(self):
        if self._has_wifi:
            return self.ssid_input.text().strip()
        return ""


class ApplyProgress(QWidget):
    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(0)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("log-output")
        layout.addWidget(self.log)

    def append(self, text, style=""):
        self.log.append(f'<span style="{style}">{text}</span>')
        scroll = self.log.verticalScrollBar()
        scroll.setValue(scroll.maximum())

    def append_step(self, label, ok, msg):
        icon = "✓" if ok else "✗"
        c = (current_theme.success if current_theme else '#16a34a') if ok else (current_theme.danger if current_theme else '#dc2626')
        self.append(f'<span style="font-weight:600;color:{c}">{icon}</span> '
                    f'<b>{label}</b>: {msg}',
                    f"color: {c};")


class WizardDialog(QDialog):
    def __init__(self, parent, api, isp_id, isp_name, isp_data):
        super().__init__(parent)
        self.api = api
        self.isp_id = isp_id
        self.isp_name = isp_name
        self.isp_data = isp_data or {}
        self.isp_slug = isp_data.get('slug', '')
        self._has_wifi = False
        self._connector = None
        self._router_controller = None
        self._step_index = 0
        self._connected = False
        self._setup_ui()
        self.setWindowTitle(f"Add Router — {isp_name}")
        self.setMinimumSize(680, 520)
        self.setModal(True)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(24, 20, 24, 16)
        top.setSpacing(0)

        title = QLabel(f"Add Router — {self.isp_name}")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        top.addWidget(title)
        top.addStretch()

        layout.addLayout(top)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(2)

        self.step_indicators = []
        for i in range(2):
            ind = StepIndicator(i, STEP_ICONS[i], STEP_TITLES[i], STEP_DESCS[i],
                                active=(i == 0))
            sidebar_layout.addWidget(ind)
            self.step_indicators.append(ind)
        sidebar_layout.addStretch()

        body.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.step_connection = ConnectionStep()
        self.step_config = None
        self.step_progress = ApplyProgress()

        self.stack.addWidget(self.step_connection)  # 0
        self.stack.addWidget(QWidget())              # 1 placeholder for config
        self.stack.addWidget(self.step_progress)     # 2

        content_layout.addWidget(self.stack, 1)

        nav = QHBoxLayout()
        nav.setContentsMargins(20, 12, 20, 16)
        nav.setSpacing(8)

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setObjectName("primary")
        self.test_btn.setCursor(Qt.PointingHandCursor)
        self.test_btn.setMinimumHeight(38)
        self.test_btn.setMaximumWidth(160)
        self.test_btn.clicked.connect(self._do_test)
        nav.addWidget(self.test_btn)

        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("secondary")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setMinimumHeight(38)
        self.back_btn.clicked.connect(self._go_back)
        nav.addWidget(self.back_btn)

        nav.addStretch()

        self.next_btn = QPushButton("Next")
        self.next_btn.setObjectName("primary")
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setMinimumHeight(38)
        self.next_btn.setMinimumWidth(120)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.next_btn)

        content_layout.addLayout(nav)

        body.addWidget(content, 1)
        layout.addLayout(body)

        self._update_nav()
        self.step_connection.connection_tested.connect(self._on_connection_tested)

    def _on_connection_tested(self, ok, msg):
        self._connected = ok
        self._update_nav()

    def _update_nav(self):
        if self._step_index == 0:
            self.test_btn.setVisible(True)
            self.back_btn.setVisible(False)
            self.next_btn.setVisible(True)
            self.next_btn.setEnabled(self._connected)
            self.next_btn.setText("Next")
        elif self._step_index == 2:
            self.test_btn.setVisible(False)
            self.back_btn.setVisible(False)
            self.next_btn.setVisible(True)
            self.next_btn.setEnabled(False)
        else:
            self.test_btn.setVisible(False)
            self.back_btn.setVisible(True)
            self.back_btn.setEnabled(True)
            self.back_btn.setText("Back")
            self.next_btn.setVisible(True)
            self.next_btn.setEnabled(True)
            is_last = self._step_index == 1
            self.next_btn.setText("Apply && Save" if is_last else "Next")

    def _do_test(self):
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing...")
        QApplication.processEvents()
        self.step_connection.trigger_test()
        self.test_btn.setEnabled(True)
        self.test_btn.setText("✓ Connected" if self._connected else "Test Connection")

    def _go_back(self):
        if self._step_index > 0:
            self._step_index -= 1
            self._show_step()

    def _go_next(self):
        if self._step_index == 0:
            if not self.step_connection.is_connected:
                return
            self._connector = self.step_connection.connector

            from routeros.configurator import RouterOSConfigurator
            tester = RouterOSConfigurator(self._connector)
            self._has_wifi = tester.has_wireless_capability()
            logger.info(f'WiFi capability detected: {self._has_wifi}')

        elif self._step_index == 1:
            if self._has_wifi and not self.step_config.wifi_ssid:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Validation", "WiFi SSID cannot be empty")
                return
            self._start_apply()
            return

        self._step_index += 1
        self._show_step()

    def _show_step(self):
        for i, ind in enumerate(self.step_indicators):
            ind.set_active(i == self._step_index)
            ind.set_done(i < self._step_index)

        if self._step_index == 1 and self.step_config is None:
                default_ssid = self.isp_name or 'Smalnets-WiFi'
                self.step_config = ConfigStep(
                    has_wifi=self._has_wifi,
                    isp_name=self.isp_name,
                    default_ssid=default_ssid,
                )
                self.stack.removeWidget(self.stack.widget(1))
                self.stack.insertWidget(1, self.step_config)

        self.stack.setCurrentIndex(self._step_index)
        self._update_nav()

    def _start_apply(self):
        self._step_index = 2
        self.stack.setCurrentIndex(2)

        for ind in self.step_indicators:
            ind.set_done(True)

        self.next_btn.setText("Provisioning...")
        self._update_nav()

        self._provision_thread = QThread(self)
        self._provision_worker = ProvisionWorker(self.api, self._connector)
        self._provision_worker.moveToThread(self._provision_thread)

        self._provision_worker.step_started.connect(self._on_step_started)
        self._provision_worker.step_result.connect(self._on_step_result)
        self._provision_worker.finished.connect(self._on_provision_finished)
        self._provision_worker.failed.connect(self._on_provision_failed)
        self._provision_thread.started.connect(lambda: self._provision_worker.run(
            isp_id=self.isp_id,
            isp_slug=self.isp_slug,
            isp_data=self.isp_data,
            host=self.step_connection.host,
            port=self.step_connection.port,
            user=self.step_connection.user,
            password=self.step_connection.password,
            wifi_ssid=self.step_config.wifi_ssid if self._has_wifi else '',
            has_wifi=self._has_wifi,
        ))
        self._provision_thread.finished.connect(self._provision_thread.deleteLater)

        self._provision_thread.start()

    def _on_provision_failed(self, msg):
        self._provision_thread.quit()
        self._provision_thread.wait()
        self.next_btn.setEnabled(True)
        self.back_btn.setEnabled(True)
        self.next_btn.setText("Provisioning Failed")

    def _on_provision_finished(self, config, router_name, router_id):
        self._provision_thread.quit()
        self._provision_thread.wait()

        self._router_controller = RouterController(self.api, self._connector)
        self._router_controller.step_started.connect(self._on_step_started)
        self._router_controller.step_result.connect(self._on_step_result)
        self._router_controller.all_done.connect(self._on_all_done)

        config['wifi_ssid'] = self.step_config.wifi_ssid if self._has_wifi else ''
        config['stripped_name'] = self.isp_data.get('stripped_name', '')
        config['old_password'] = self.step_connection.password
        config['routeros_host'] = self.step_connection.host
        config['routeros_user'] = self.step_connection.user

        self._on_step_started("Starting remaining configuration steps")
        self._on_step_result("Starting remaining configuration steps", True, "")
        self._router_controller.apply_configuration(config)

    def _on_step_started(self, label):
        c = current_theme.text_secondary if current_theme else '#64748b'
        self.step_progress.append(f'<b>{label}</b>', f'color: {c};')

    def _on_step_result(self, label, ok, msg):
        self.step_progress.append_step(label, ok, msg)

    def _on_all_done(self, success, msg):
        if success:
            c = current_theme.success if current_theme else '#16a34a'
            self.step_progress.append(
                f'<b style="color:{c}">✓ Configuration complete</b>')
        else:
            c = current_theme.danger if current_theme else '#dc2626'
            self.step_progress.append(
                f'<b style="color:{c}">✗ Failed: {msg}</b>')

        self.next_btn.setText("Finish")
        self.next_btn.setObjectName("primary")
        self.next_btn.setEnabled(True)
        with contextlib.suppress(TypeError):
            self.next_btn.clicked.disconnect()
        self.next_btn.clicked.connect(self.accept)
