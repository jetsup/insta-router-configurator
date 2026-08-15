import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from views.styles import current_theme

logger = logging.getLogger(__name__)

# Embedded server URL — no need to ask users
SERVER_URL = "https://smalnets.ddns.net"


class PasswordField(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hidden = True
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Enter password")
        self.entry.setEchoMode(QLineEdit.Password)
        self.entry.setStyleSheet("padding-right: 36px;")
        self.toggle_btn = QPushButton("👁")
        self.toggle_btn.setObjectName("icon-btn")
        self.toggle_btn.setFixedSize(32, 32)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle)
        self.toggle_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; font-size: 16px; }
            QPushButton:hover { border-radius: 4px; }
        """)
        layout.addWidget(self.entry)
        layout.addWidget(self.toggle_btn)

    def _toggle(self):
        self._hidden = not self._hidden
        self.entry.setEchoMode(QLineEdit.Password if self._hidden else QLineEdit.Normal)
        self.toggle_btn.setText("👁" if self._hidden else "👁‍🗨")

    def text(self):
        return self.entry.text()

    def setText(self, text):
        self.entry.setText(text)

    def clear(self):
        self.entry.clear()

    def setFocus(self):
        self.entry.setFocus()


class OtpInput(QWidget):
    """Six individual digit boxes for entering a one-time code."""

    return_pressed = Signal()
    all_filled = Signal()

    def __init__(self, digit_count=6, parent=None):
        super().__init__(parent)
        self._digits: list[QLineEdit] = []
        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        for i in range(digit_count):
            box = QLineEdit()
            box.setMaxLength(1)
            box.setFixedSize(48, 56)
            box.setAlignment(Qt.AlignCenter)
            box.setStyleSheet(
                "font-size: 24px; font-weight: 700; letter-spacing: 0px; "
                "border-radius: 8px; padding: 0px;"
            )
            box.textChanged.connect(lambda text, idx=i: self._on_text_changed(text, idx))
            box.returnPressed.connect(self.return_pressed.emit)
            box.installEventFilter(self)
            self._digits.append(box)
            layout.addWidget(box)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress and obj in self._digits:
            idx = self._digits.index(obj)
            if event.key() == Qt.Key_Backspace:
                if not obj.text() and idx > 0:
                    self._digits[idx - 1].setFocus()
                    self._digits[idx - 1].clear()
                elif obj.text():
                    obj.clear()
                return True
            if event.key() in (Qt.Key_Left,):
                if idx > 0:
                    self._digits[idx - 1].setFocus()
                    self._digits[idx - 1].selectAll()
                return True
            if event.key() in (Qt.Key_Right,):
                if idx < len(self._digits) - 1:
                    self._digits[idx + 1].setFocus()
                    self._digits[idx + 1].selectAll()
                return True
        return super().eventFilter(obj, event)

    def _on_text_changed(self, text: str, idx: int):
        if text and (not text.isupper() or len(text) > 1):
            cleaned = text.upper()[-1:]
            self._digits[idx].blockSignals(True)
            self._digits[idx].setText(cleaned)
            self._digits[idx].blockSignals(False)

        if text and idx < len(self._digits) - 1:
            self._digits[idx + 1].setFocus()
            self._digits[idx + 1].selectAll()

        if all(d.text() for d in self._digits):
            self.all_filled.emit()

    def code(self) -> str:
        return ''.join(d.text() for d in self._digits)

    def clear(self):
        for d in self._digits:
            d.clear()
        if self._digits:
            self._digits[0].setFocus()

    def setFocus(self):
        if self._digits:
            self._digits[0].setFocus()


class TwoFactorWidget(QWidget):
    verified = Signal()

    def __init__(self, auth, email):
        super().__init__()
        self.auth = auth
        self.email = email
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("card")
        self.setFixedWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        label = QLabel("Two-Factor Authentication")
        label.setObjectName("login-logo")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        info = QLabel(f"A verification code was sent to {self.email}")
        info.setObjectName("login-subtitle")
        info.setAlignment(Qt.AlignCenter)
        info.setWordWrap(True)
        layout.addWidget(info)

        sep = QFrame()
        sep.setObjectName("login-separator")
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        fields = QVBoxLayout()
        fields.setSpacing(14)

        fields.addWidget(self._labeled("Verification Code"))

        otp_row = QHBoxLayout()
        otp_row.setAlignment(Qt.AlignCenter)
        self.code_input = OtpInput()
        self.code_input.return_pressed.connect(self._do_verify)
        self.code_input.all_filled.connect(self._do_verify)
        otp_row.addWidget(self.code_input)
        fields.addLayout(otp_row)

        layout.addLayout(fields)
        layout.addSpacing(20)

        self.verify_btn = QPushButton("Verify & Continue")
        self.verify_btn.setObjectName("primary")
        self.verify_btn.setCursor(Qt.PointingHandCursor)
        self.verify_btn.setMinimumHeight(44)
        self.verify_btn.clicked.connect(self._do_verify)
        layout.addWidget(self.verify_btn)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedHeight(24)
        layout.addWidget(self.status_label)

    def _labeled(self, text):
        label = QLabel(text)
        label.setObjectName("field-label")
        return label

    def _do_verify(self):
        code = self.code_input.code()
        if len(code) < 6:
            self.status_label.setText("Enter all 6 digits")
            self.status_label.setStyleSheet(f"color: {(current_theme.danger if current_theme else '#dc2626')}; font-size: 12px;")
            return

        self.verify_btn.setEnabled(False)
        self.verify_btn.setText("Verifying...")
        self.status_label.setText("")

        QTimer.singleShot(50, lambda: self._perform_verify(code))

    def _perform_verify(self, code):
        success, msg = self.auth.verify_two_factor(self.email, code)
        if success:
            self.status_label.setText("✓ Verified")
            self.status_label.setStyleSheet(f"color: {(current_theme.success if current_theme else '#16a34a')}; font-size: 12px;")
            QTimer.singleShot(300, self.verified.emit)
        else:
            self.status_label.setText(msg)
            self.status_label.setStyleSheet(f"color: {(current_theme.danger if current_theme else '#dc2626')}; font-size: 12px;")
            self.verify_btn.setEnabled(True)
            self.verify_btn.setText("Verify & Continue")
            self.code_input.clear()
            self.code_input.setFocus()


class LoginView(QWidget):
    login_successful = Signal()

    def __init__(self, auth):
        super().__init__()
        self.auth = auth
        self._pending_email = None
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(0)

        self.auth.base_url = SERVER_URL

        # Login form card
        self.login_card = QWidget()
        self.login_card.setObjectName("card")
        self.login_card.setFixedWidth(420)
        card = QVBoxLayout(self.login_card)
        card.setSpacing(0)
        card.setContentsMargins(32, 32, 32, 32)

        logo = QLabel("⚡ Smalnets")
        logo.setObjectName("login-logo")
        logo.setAlignment(Qt.AlignCenter)
        card.addWidget(logo)

        subtitle = QLabel("Router Configuration Tool")
        subtitle.setObjectName("login-subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        card.addWidget(subtitle)

        sep = QFrame()
        sep.setObjectName("login-separator")
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        card.addWidget(sep)

        fields = QVBoxLayout()
        fields.setSpacing(14)

        fields.addWidget(self._labeled("Email"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("admin@example.com")
        fields.addWidget(self.email_input)

        fields.addWidget(self._labeled("Password"))
        self.password_field = PasswordField()
        fields.addWidget(self.password_field)

        card.addLayout(fields)
        card.addSpacing(20)

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setObjectName("primary")
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setMinimumHeight(44)
        self.login_btn.clicked.connect(self.do_login)
        card.addWidget(self.login_btn)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedHeight(24)
        card.addWidget(self.status_label)

        # 2FA card (stack widget manages visibility, no need to hide explicitly)
        self.two_factor_card = TwoFactorWidget(self.auth, "")
        self.two_factor_card.verified.connect(self._on_two_factor_verified)

        # Stack to switch between login and 2FA
        self.stack = QStackedWidget()
        login_container = QWidget()
        login_container.setObjectName("page")
        login_container.setLayout(QHBoxLayout())
        login_container.layout().setAlignment(Qt.AlignCenter)
        login_container.layout().setContentsMargins(0, 0, 0, 0)
        login_container.layout().addWidget(self.login_card)
        twofa_container = QWidget()
        twofa_container.setObjectName("page")
        twofa_container.setLayout(QHBoxLayout())
        twofa_container.layout().setAlignment(Qt.AlignCenter)
        twofa_container.layout().setContentsMargins(0, 0, 0, 0)
        twofa_container.layout().addWidget(self.two_factor_card)
        self.stack.addWidget(login_container)
        self.stack.addWidget(twofa_container)
        layout.addWidget(self.stack)

        self.password_field.entry.returnPressed.connect(self.do_login)

    def _labeled(self, text):
        label = QLabel(text)
        label.setObjectName("field-label")
        return label

    def do_login(self):
        email = self.email_input.text().strip()
        password = self.password_field.text()

        if not email or not password:
            self.status_label.setText("All fields are required")
            self.status_label.setStyleSheet(f"color: {(current_theme.danger if current_theme else '#dc2626')}; font-size: 12px;")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Signing in...")
        self.status_label.setText("")

        QTimer.singleShot(50, lambda: self._perform_login(email, password))

    def _perform_login(self, email, password):
        success, two_factor_email, msg = self.auth.login(email, password)
        if success:
            if two_factor_email:
                self._pending_email = two_factor_email
                self._show_two_factor()
                return
            self.status_label.setText("✓ Login successful")
            self.status_label.setStyleSheet(f"color: {(current_theme.success if current_theme else '#16a34a')}; font-size: 12px;")
            QTimer.singleShot(300, self.login_successful.emit)
        else:
            self.status_label.setText(msg)
            self.status_label.setStyleSheet(f"color: {(current_theme.danger if current_theme else '#dc2626')}; font-size: 12px;")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Sign In")

    def _show_two_factor(self):
        self.two_factor_card.email = self._pending_email
        self.two_factor_card.code_input.clear()
        self.two_factor_card.status_label.setText("")
        self.two_factor_card.verify_btn.setEnabled(True)
        self.two_factor_card.verify_btn.setText("Verify & Continue")
        self.stack.setCurrentIndex(1)
        self.two_factor_card.code_input.setFocus()

    def _on_two_factor_verified(self):
        cnt = current_theme
        self.status_label.setText("✓ Verified")
        self.status_label.setStyleSheet(f"color: {(cnt.success if cnt else '#16a34a')}; font-size: 12px;")
        QTimer.singleShot(300, self.login_successful.emit)
