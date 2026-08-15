import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class SplashOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        self._title = QLabel("Smalnets Config Tool")
        self._title.setStyleSheet("font-size: 22px; font-weight: 800; letter-spacing: -0.3px;")
        layout.addWidget(self._title, 0, Qt.AlignCenter)

        self._subtitle = QLabel("Connecting to your network...")
        self._subtitle.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._subtitle, 0, Qt.AlignCenter)

        self._spinner = QProgressBar()
        self._spinner.setRange(0, 0)
        self._spinner.setFixedSize(200, 4)
        self._spinner.setTextVisible(False)
        layout.addWidget(self._spinner, 0, Qt.AlignCenter)

        self._dots = 0
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._animate_dots)
        self._dot_timer.start(500)

    def _animate_dots(self):
        self._dots = (self._dots + 1) % 4
        if self._dots == 0:
            self._subtitle.setText("Connecting to your network")
        else:
            self._subtitle.setText(f"Connecting to your network{'.' * self._dots}")

    def stop(self):
        self._dot_timer.stop()
        self._subtitle.setText("Connected")
