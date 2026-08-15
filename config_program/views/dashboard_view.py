import contextlib
import logging
import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

try:
    from api.updater import (
        VERSION,
        check_for_updates,
        download_update,
        get_current_version,
    )
except ImportError:
    VERSION = "0.0.0"

    def get_current_version():
        return VERSION

    def check_for_updates():
        return None

    def download_update(url):
        return None



def _display_version() -> str:
    return get_current_version() or VERSION


class RoutersWidget(QWidget):
    add_router_requested = Signal(int, str, dict)
    loaded = Signal()

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.isp_id = None
        self.isp_slug = None
        self.isp_name = ""
        self.isp_data = {}
        self._all_routers = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)

        self.title = QLabel("Routers")
        self.title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(self.title)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, model or VPN IP...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumHeight(38)
        self.search_input.textChanged.connect(self._filter_routers)
        header.addWidget(self.search_input)

        self.add_btn = QPushButton("Add Router")
        self.add_btn.setObjectName("primary")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setMinimumHeight(38)
        self.add_btn.clicked.connect(self._do_add)
        header.addWidget(self.add_btn)

        layout.addLayout(header)

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedHeight(4)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setVisible(False)
        layout.addWidget(self.loading_bar)

        self.tree_stack = QStackedWidget()

        self.placeholder = QLabel("Select an ISP to view its routers")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("font-size: 14px;")
        self.tree_stack.addWidget(self.placeholder)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["ID", "Name", "Model", "Firmware", "VPN IP", "Status"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.setAnimated(True)
        self.tree.itemDoubleClicked.connect(self._on_router_double_click)
        h = self.tree.header()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.tree_stack.addWidget(self.tree)

        self.tree_stack.setCurrentIndex(0)
        layout.addWidget(self.tree_stack)

    def set_isp(self, isp_id, isp_name, isp_data):
        self.isp_id = isp_id
        self.isp_slug = isp_data.get('slug', '')
        self.isp_name = isp_name
        self.isp_data = isp_data
        short = (isp_name[:8] + "…") if len(isp_name) > 8 else isp_name
        self.title.setText(f"Routers — {short}")
        self.search_input.setVisible(True)
        self.add_btn.setVisible(True)
        self._load()

    def clear_isp(self):
        self.isp_id = None
        self.isp_slug = None
        self.isp_name = ""
        self.isp_data = {}
        self._all_routers = []
        self.title.setText("Routers")
        self.search_input.clear()
        self.tree.clear()
        self.loading_bar.setVisible(False)
        self.tree_stack.setCurrentIndex(0)

    def load_for_isp(self, isp_id, isp_name, isp_data):
        """Load routers directly without requiring ISP selection (for ISP users)."""
        self.isp_id = isp_id
        self.isp_slug = isp_data.get('slug', '')
        self.isp_name = isp_name
        self.isp_data = isp_data
        self.title.setText(f"My Routers — {isp_name}")
        self.search_input.setVisible(True)
        self.add_btn.setVisible(True)
        self.placeholder.setText("Loading your routers...")
        self._load()

    def _load(self):
        self.add_btn.setEnabled(False)
        self.add_btn.setText("Loading...")
        self.loading_bar.setVisible(True)
        self.tree.clear()
        QTimer.singleShot(50, self._do_load)

    def _do_load(self):
        try:
            self._all_routers = self.api.get_isp_routers(self.isp_slug)
            self._populate_tree(self._all_routers)
            if self._all_routers:
                self.tree_stack.setCurrentIndex(1)
            else:
                self.placeholder.setText("No routers configured yet.")
                self.tree_stack.setCurrentIndex(0)
            logger.info(f'Loaded {len(self._all_routers)} routers for ISP {self.isp_id}')
        except Exception as e:
            logger.error(f'Failed to load routers: {e}', exc_info=True)
        finally:
            self.add_btn.setEnabled(True)
            self.add_btn.setText("Add Router")
            self.loading_bar.setVisible(False)
            self.loaded.emit()

    def _populate_tree(self, routers):
        self.tree.clear()
        for i, r in enumerate(routers):
            item = QTreeWidgetItem()
            item.setText(0, str(i + 1))
            item.setText(1, r.get("name", ""))
            item.setText(2, r.get("model", ""))
            item.setText(3, r.get("firmware_version", ""))
            item.setText(4, r.get("vpn_ip", ""))
            item.setText(5, r.get("status", "unknown"))
            self.tree.addTopLevelItem(item)

    def _filter_routers(self, text):
        if not text.strip():
            self._populate_tree(self._all_routers)
            return
        q = text.strip().lower()
        filtered = [
            r for r in self._all_routers
            if q in r.get("name", "").lower()
            or q in r.get("model", "").lower()
            or q in r.get("vpn_ip", "").lower()
        ]
        self._populate_tree(filtered)

    def _on_router_double_click(self, item):
        if not self.isp_id:
            return
        # Find the router index from the tree item
        index = self.tree.indexOfTopLevelItem(item)
        if index < 0 or index >= len(self._all_routers):
            return
        router = self._all_routers[index]
        router_id = router.get('id')
        router_name = router.get('name', 'Unknown')

        if not router_id:
            return

        logger.info(f'Router double-clicked: id={router_id}, name={router_name}')

        from views.router_settings_view import RouterSettingsDialog
        dialog = RouterSettingsDialog(self.window(), self.api, router_id, router_name)
        dialog.exec()

    def _do_add(self):
        if not self.isp_id:
            return
        logger.info(f'Add router requested for ISP {self.isp_id} ({self.isp_name})')
        self.add_router_requested.emit(self.isp_id, self.isp_name, self.isp_data)


class DashboardView(QWidget):
    logout_requested = Signal()
    open_wizard = Signal(int, str, dict)
    loaded = Signal()

    def __init__(self, api, app=None):
        super().__init__()
        self.api = api
        self._app = app
        self._isps = []
        self._is_isp_mode = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(0)

        top = QHBoxLayout()
        top.setSpacing(12)

        title = QLabel("Router Configuration Tool")
        title.setStyleSheet("font-size: 22px; font-weight: 800; letter-spacing: -0.3px;")
        top.addWidget(title)
        top.addStretch()

        self._build_user_menu(top)

        layout.addLayout(top)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        content = QHBoxLayout()
        content.setSpacing(20)
        content.setContentsMargins(0, 16, 0, 0)

        # ISP tree (hidden in ISP mode)
        self.isp_panel = QWidget()
        isp_layout = QVBoxLayout(self.isp_panel)
        isp_layout.setSpacing(8)
        isp_layout.setContentsMargins(0, 0, 0, 0)

        isp_top = QHBoxLayout()
        isp_top.setSpacing(8)
        isp_label = QLabel("ISP")
        isp_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        isp_top.addWidget(isp_label)
        isp_top.addStretch()

        self.isp_search = QLineEdit()
        self.isp_search.setPlaceholderText("Search ISP...")
        self.isp_search.setClearButtonEnabled(True)
        self.isp_search.setMinimumHeight(38)
        self.isp_search.textChanged.connect(self._filter_isps)
        isp_top.addWidget(self.isp_search, 1)

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setObjectName("icon-btn")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setToolTip("Refresh ISPs")
        self.refresh_btn.setFixedSize(34, 34)
        self.refresh_btn.clicked.connect(self._refresh)
        isp_top.addWidget(self.refresh_btn)

        isp_layout.addLayout(isp_top)

        self.isp_tree = QTreeWidget()
        self.isp_tree.setColumnCount(4)
        self.isp_tree.setHeaderLabels(["ID", "Business Name", "Contact", "Routers"])
        self.isp_tree.setAlternatingRowColors(True)
        self.isp_tree.setRootIsDecorated(False)
        self.isp_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.isp_tree.setAnimated(True)
        self.isp_tree.itemClicked.connect(self._on_isp_selected)
        self.isp_tree.setMinimumWidth(320)
        h = self.isp_tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        isp_layout.addWidget(self.isp_tree, 1)

        content.addWidget(self.isp_panel, 2)

        right = QVBoxLayout()
        right.setSpacing(0)

        self.routers_widget = RoutersWidget(self.api)
        self.routers_widget.add_router_requested.connect(self.open_wizard.emit)
        self.routers_widget.loaded.connect(self.loaded.emit)
        right.addWidget(self.routers_widget, 1)

        content.addLayout(right, 3)

        layout.addLayout(content, 1)

    def _build_user_menu(self, parent_layout):
        user_data = self.api.auth.user or {}
        user_name = user_data.get('name', user_data.get('email', 'User'))
        avatar_char = user_name[0].upper() if user_name else 'U'

        self.user_btn = QPushButton(f"{avatar_char}  {user_name}  ▾")
        self.user_btn.setObjectName("user-btn")
        self.user_btn.setCursor(Qt.PointingHandCursor)
        self.user_btn.setMinimumHeight(38)

        self.user_menu = QMenu(self.user_btn)

        roles = user_data.get('roles', [])
        role_label = " | ".join(r.replace('ROLE_', '') for r in roles) if roles else "User"
        role_action = QAction(f"🔑  {role_label}", self)
        role_action.setEnabled(False)
        self.user_menu.addAction(role_action)

        self.user_menu.addSeparator()

        self.theme_action = QAction(self._theme_toggle_text(), self)
        self.theme_action.triggered.connect(self._toggle_theme)
        self.user_menu.addAction(self.theme_action)

        self.user_menu.addSeparator()

        check_update_action = QAction("📥  Check for Updates", self)
        check_update_action.triggered.connect(self.check_for_updates_now)
        self.user_menu.addAction(check_update_action)

        about_action = QAction("ℹ️  About Smalnets", self)
        about_action.triggered.connect(self._show_about_dialog)
        self.user_menu.addAction(about_action)

        self.user_menu.addSeparator()

        logout_action = QAction("🚪  Logout", self)
        logout_action.triggered.connect(self.logout_requested.emit)
        self.user_menu.addAction(logout_action)

        self.user_btn.setMenu(self.user_menu)
        parent_layout.addWidget(self.user_btn)

    def _refresh(self):
        self.refresh_btn.setEnabled(False)
        QTimer.singleShot(50, self._do_refresh)

    def _do_refresh(self):
        try:
            self._isps = sorted(self.api.get_isps(), key=lambda x: x.get('id', 0))
            self._populate_isp_tree(self._isps)
            logger.info(f'Loaded {len(self._isps)} ISPs')
        except Exception as e:
            logger.error(f'Failed to load ISPs: {e}', exc_info=True)
        finally:
            self.refresh_btn.setEnabled(True)
            self.loaded.emit()

    def _populate_isp_tree(self, isps):
        self.isp_tree.clear()
        for isp in isps:
            item = QTreeWidgetItem()
            item.setText(0, str(isp.get("id", "")))
            item.setText(1, isp.get("business_name", ""))
            item.setText(2, isp.get("contact_person", ""))
            item.setText(3, str(isp.get("routers_count", 0)))
            self.isp_tree.addTopLevelItem(item)

    def _filter_isps(self, text):
        if not text.strip():
            self._populate_isp_tree(self._isps)
            return
        q = text.strip().lower()
        filtered = [
            isp for isp in self._isps
            if q in isp.get("business_name", "").lower()
            or q in isp.get("contact_person", "").lower()
        ]
        self._populate_isp_tree(filtered)

    def _on_isp_selected(self):
        selected = self.isp_tree.currentItem()
        if not selected:
            return
        isp_id = int(selected.text(0))
        isp_name = selected.text(1)
        isp_data = next((isp for isp in self._isps if isp.get('id') == isp_id), {})
        logger.info(f'Selected ISP: id={isp_id}, name={isp_name}')

        self.routers_widget.set_isp(isp_id, isp_name, isp_data)

    def _deselect_isp(self):
        self.isp_tree.clearSelection()
        self.routers_widget.clear_isp()

    def load(self):
        self._is_isp_mode = self.api.auth.is_isp and not self.api.auth.is_admin

        if self._is_isp_mode:
            # ISP mode: hide ISP tree, auto-load own routers
            self.isp_panel.setVisible(False)
            self._load_isp_routers()
        else:
            # Admin mode: show ISP tree
            self.isp_panel.setVisible(True)
            QTimer.singleShot(50, self._do_refresh)

    def _load_isp_routers(self):
        """Load routers for the current ISP user."""
        try:
            isps = self.api.get_isps()
            if not isps:
                QMessageBox.warning(self, "No ISP", "No ISP record found for your account.")
                return
            isp = isps[0]
            self.routers_widget.load_for_isp(
                isp['id'], isp['business_name'],
                isp,
            )
        except Exception as e:
            logger.error(f'Failed to load ISP routers: {e}', exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to load routers: {e}")

    def _theme_toggle_text(self) -> str:
        if not self._app:
            return "🌙  Switch to Dark"
        pref = self._app.theme_preference
        if pref == 'light':
            return "🌙  Switch to Dark"
        if pref == 'dark':
            return "🖥  Follow System"
        return "☀️  Switch to Light"

    def _toggle_theme(self):
        if self._app:
            self._app.toggle_theme()
            self.theme_action.setText(self._theme_toggle_text())

    def autocheck_for_updates(self):
        logger.info('Auto-checking for updates...')
        release = check_for_updates()
        if release:
            logger.info(f'Update available: v{release["version"]}')
            self._show_update_dialog(release, auto=True)

    def check_for_updates_now(self):
        logger.info('Manual update check triggered')
        release = check_for_updates()
        if release:
            self._show_update_dialog(release, auto=False)
        else:
            QMessageBox.information(self, "Up-to-Date", f"You are running the latest version (v{_display_version()}).")

    def _show_about_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("About Smalnets")
        dialog.setFixedSize(480, 340)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        title = QLabel("Smalnets Config Tool")
        title.setStyleSheet("font-size: 20px; font-weight: 800;")
        layout.addWidget(title)

        release_info = check_for_updates()
        latest = release_info['version'] if release_info else _display_version()

        details = QTextBrowser()
        details.setOpenExternalLinks(True)
        details.setHtml(f"""
        <p><b>Version:</b> v{_display_version()}</p>
        <p><b>Latest Release:</b> v{latest}</p>
        <p><b>Description:</b> The official desktop application for configuring and
        managing MikroTik routers. Provides connection testing, password management,
        VPN/WireGuard setup, GenieACS integration, RADIUS NAS registration, and
        hotspot provisioning.</p>
        <p><b>Built with:</b> Python, PySide6</p>
        <p><b>Website:</b> <a href="https://smalnets.ddns.net">smalnets.ddns.net</a></p>
        """)
        layout.addWidget(details, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary")
        close_btn.clicked.connect(dialog.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        dialog.exec()

    def _show_update_dialog(self, release: dict, auto: bool = False):
        dialog = QDialog(self)
        dialog.setWindowTitle("Update Available" if not auto else "Update Available")
        dialog.setFixedSize(400, 220)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        title = QLabel(f"📥  Smalnets v{release['version']} is available!")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        info = QLabel(f"You are currently running v{_display_version()}.")
        info.setStyleSheet("")
        layout.addWidget(info)

        buttons = QHBoxLayout()
        buttons.addStretch()

        skip = QPushButton("Later")
        skip.clicked.connect(dialog.reject)
        buttons.addWidget(skip)

        dl_btn = QPushButton("Download")
        dl_btn.setObjectName("primary")
        dl_btn.clicked.connect(lambda: self._do_update(release, dialog))
        buttons.addWidget(dl_btn)

        layout.addLayout(buttons)
        dialog.exec()

    def _do_update(self, release: dict, parent_dialog: QDialog):
        parent_dialog.accept()
        progress = QProgressDialog("Downloading update...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Updating Smalnets")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        QTimer.singleShot(100, lambda: self._perform_download(release, progress))

    def _perform_download(self, release: dict, progress: QProgressDialog):
        path = download_update(release['download_url'])
        if progress.wasCanceled():
            if path:
                with contextlib.suppress(Exception):
                    os.unlink(path)
            return
        progress.close()
        if path:
            from api.updater import apply_update
            if apply_update(path):
                QMessageBox.information(self, "Update Ready",
                    "The update has been downloaded. The app will now restart to apply it.")
                import sys
                sys.exit(0)
            else:
                QMessageBox.information(self, "Download Complete",
                    f"The new version has been saved.\n\nFor manual installation, run:\n{path}")
        else:
            QMessageBox.warning(self, "Download Failed",
                "Failed to download the update. Please try again later or visit our website.")
