import json
import logging
import os
import sys
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import api.updater as _updater  # noqa: F401 – ensure Nuitka bundles updater module
from api.auth import Auth
from api.client import ApiClient
from api.updater import get_current_version
from views.dashboard_view import DashboardView
from views.login_view import LoginView
from views.splash import SplashOverlay
from views.styles import DARK, LIGHT, build_qss
from views.wizard_view import WizardDialog

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.expanduser('~/.config/smalnets')
PREFS_FILE = os.path.join(CONFIG_DIR, 'preferences.json')


def _detect_system_theme() -> str:
    try:
        app = QApplication.instance()
        if app is None:
            return 'light'
        hints = app.styleHints()
        if hasattr(hints, 'colorScheme'):
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return 'dark'
    except Exception:
        pass
    return 'light'


def _load_theme_preference() -> str:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(PREFS_FILE) as f:
            return json.load(f).get('theme', 'system')
    except Exception:
        return 'system'


def _save_theme_preference(name: str):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(PREFS_FILE, 'w') as f:
            json.dump({'theme': name}, f)
    except Exception as e:
        logger.warning(f'Failed to save theme preference: {e}')


def _resolve_theme(pref: str):
    if pref == 'dark':
        return DARK
    if pref == 'light':
        return LIGHT
    return DARK if _detect_system_theme() == 'dark' else LIGHT


def get_asset_path(relative_path):
    """Get absolute path to resource, works for dev and for compiled binaries"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class SmalnetsConfigApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smalnets Router Configuration Tool")
        self.setMinimumSize(1100, 700)
        self.resize(1180, 740)

        self._theme_preference = _load_theme_preference()
        self._theme = _resolve_theme(self._theme_preference)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.auth = Auth(base_url="https://smalnets.ddns.net")
        self.api = ApiClient(self.auth)

        logger.info(f'App starting, default server URL: {self.auth.base_url}')
        logger.info(f'Theme preference: {self._theme_preference}, resolved: {self._theme.name}')

    def apply_theme(self):
        global current_theme
        current_theme = self._theme
        app = QApplication.instance()
        app.setStyleSheet("")
        app.setStyleSheet(build_qss(self._theme))

    def toggle_theme(self):
        cycle = {'light': 'dark', 'dark': 'system', 'system': 'light'}
        self._theme_preference = cycle.get(self._theme_preference, 'light')
        self._theme = _resolve_theme(self._theme_preference)
        _save_theme_preference(self._theme_preference)
        self.apply_theme()
        logger.info(f'Theme toggled to preference={self._theme_preference}, resolved={self._theme.name}')

    @property
    def theme(self):
        return self._theme

    @property
    def theme_preference(self):
        return self._theme_preference

    def start(self):
        self.apply_theme()
        if self.auth.token:
            logger.info('Saved token found, attempting auto-login...')
            QTimer.singleShot(100, self._try_auto_login)
        else:
            self._show_login()

    def _try_auto_login(self):
        logger.info('Verifying saved token...')
        ok = self.auth.verify_token()
        if ok:
            logger.info('Token valid, going straight to dashboard')
            self._show_dashboard()
        else:
            logger.info('Token invalid/expired, showing login')
            self._show_login()

    def _clear_stack(self):
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            if w:
                w.deleteLater()

    def _show_login(self):
        logger.info('Showing login screen')
        self._clear_stack()
        self.login_view = LoginView(self.auth)
        self.login_view.login_successful.connect(self._show_dashboard)
        self.stack.addWidget(self.login_view)
        self.stack.setCurrentWidget(self.login_view)

    def _show_dashboard(self):
        logger.info('Showing dashboard')
        self._clear_stack()
        self.dashboard_view = DashboardView(self.api, self)
        self.dashboard_view.logout_requested.connect(self._on_logout)
        self.dashboard_view.open_wizard.connect(self._open_wizard)
        self.dashboard_view.loaded.connect(self._hide_splash)
        self.stack.addWidget(self.dashboard_view)
        self.stack.setCurrentWidget(self.dashboard_view)
        self._show_splash()
        self.dashboard_view.load()

    def _show_splash(self):
        self._splash_start = time.monotonic()
        self._splash = SplashOverlay(self)
        self._splash.setGeometry(self.rect())
        self._splash.raise_()
        self._splash.show()

    def _hide_splash(self):
        if not self._splash:
            return
        elapsed = time.monotonic() - self._splash_start
        remaining = 5.0 - elapsed
        if remaining > 0:
            QTimer.singleShot(int(remaining * 1000), self._do_hide_splash)
        else:
            self._do_hide_splash()

    def _do_hide_splash(self):
        if self._splash:
            self._splash.stop()
            self._splash.hide()
            self._splash.deleteLater()
            self._splash = None
        if hasattr(self, 'dashboard_view'):
            QTimer.singleShot(200, self.dashboard_view.autocheck_for_updates)

    def _open_wizard(self, isp_id: int, isp_name: str, isp_data: dict):
        logger.info(f'Opening wizard for ISP id={isp_id} name={isp_name}')
        wizard = WizardDialog(self, self.api, isp_id, isp_name, isp_data)
        wizard.accepted.connect(self.dashboard_view.load)
        wizard.show()

    def _on_logout(self):
        logger.info('Logging out')
        self.auth.logout()
        self._show_login()


if __name__ == "__main__":
    try:
        if any(a in sys.argv for a in ('--version', '-v')):
            print(f"Smalnets Config Tool {get_current_version()}")
            sys.exit(0)

        logger.info('=' * 50)
        logger.info('Smalnets Config Tool starting up')
        logger.info(f'Python version: {sys.version}')
        logger.info('=' * 50)
        app = QApplication(sys.argv)

        # CRUCIAL FOR LINUX TASKBAR TRACKING:
        # This string MUST match the exact filename of your .desktop file (minus the extension)
        app.setDesktopFileName("smalnets")

        app_icon = QIcon(get_asset_path("assets/images/logo.png"))
        app.setWindowIcon(app_icon) # Sets the icon for the app window and taskbar
        app.setStyle("Fusion")
        window = SmalnetsConfigApp()
        window.show()
        window.start()
        sys.exit(app.exec())
    except KeyboardInterrupt:
        logger.info('App interrupted by user, exiting')
    except Exception as e:
        logger.error(f'Unexpected error in main: {e}', exc_info=True)
