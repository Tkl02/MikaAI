import sys
import os
import importlib
from PyQt6.QtCore import pyqtSignal, QObject, pyqtSlot
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit, QLabel)
from PyQt6.QtGui import QTextCursor
from loguru import logger
from mika_core.MikaWindows import MikaWindows
from mika_core import MikaBrain

NEON_MAGENTA = "#ff00ff"
NEON_CYAN = "#00ffff"
NEON_GREEN = "#00ff00"
DARK_BG = "#121212"
PANEL_BG = "#1e1e1e"

class QtLogHandler(QObject):
    new_log = pyqtSignal(str)

    def write(self, message):
        self.new_log.emit(message)
    
class MikaDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mika_windows = None
        self.mika_brain = None
        self.init_ui()
        self.setup_logger()

    def setup_logger(self):
        self.log_handler = QtLogHandler()
        self.log_handler.new_log.connect(self.update_terminal)
        logger.add(self.log_handler.write, format="{time:HH:mm:ss} | {level} | {message}")

    def init_ui(self):
        self.setWindowTitle("Mika AI - Control Dashboard")
        self.resize(900,500)
        self.setStyleSheet(f"background-color: {DARK_BG}; color: white; font-family: 'Consolas', monospace;")

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        control_panel = QVBoxLayout()
        title = QLabel("Mika Control")
        title.setStyleSheet(f"color: {NEON_CYAN}; font-size: 20px; font-weight: bold; margin-bottom: 20px;")
        control_panel.addWidget(title)

        self.btn_start = QPushButton("START MIKA")
        self.style_button(self.btn_start, NEON_GREEN)
        self.btn_start.clicked.connect(self.start_mika)
        control_panel.addWidget(self.btn_start)

        self.btn_stop = QPushButton("STOP MIKA")
        self.style_button(self.btn_stop, NEON_MAGENTA)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_mika)
        control_panel.addWidget(self.btn_stop)

        self.btn_reload = QPushButton("HOT-RELOAD")
        self.style_button(self.btn_reload, NEON_CYAN)
        self.btn_reload.clicked.connect(self.reload_mika)
        control_panel.addWidget(self.btn_reload)

        control_panel.addStretch()
        layout.addLayout(control_panel, 1)

        terminal_layout = QVBoxLayout()
        terminal_label = QLabel("SYSTEM LOGS")
        terminal_label.setStyleSheet(f"color: {NEON_MAGENTA}; font-weight: bold;")
        terminal_layout.addWidget(terminal_label)

        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setStyleSheet(f"""
            background-color: #000000;
            color: #00ff00;
            border: 1px solid {NEON_CYAN};
            font-size: 12px
        """)
        terminal_layout.addWidget(self.terminal)
        layout.addLayout(terminal_layout,2)

    def style_button(self, btn, color):
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: 2px solid {color};
                padding: 15px;
                font-weight: bold;
                font-size: 14px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {color};
                color: black;
            }}
            QPushButton:disabled {{
                border-color: #444;
                color: #444;
            }}
    """)
        
    @pyqtSlot(str)
    def update_terminal(self, message):
        self.terminal.appendPlainText(message.strip())
        self.terminal.moveCursor(QTextCursor.MoveOperation.End)
    
    def start_mika(self):
        if not self.mika_windows:
            logger.info("Iniciando Interface VRM ...")
            self.mika_windows = MikaWindows()
            self.mika_windows.show()
        elif self.mika_windows.isHidden(): # Se foi fechada, reabre.
            self.mika_windows.show()
    
        if not self.mika_brain:
            logger.info("Iniciando cerebro da Mika ...")
            importlib.reload(MikaBrain)
            self.mika_brain = MikaBrain.MikaBrain(self.mika_windows)
            self.mika_brain.change_anim.connect(self.mika_windows.update_expression)
            self.mika_brain.change_talking_state.connect(self.mika_windows.set_talking)

            self.mika_windows.brain = self.mika_brain

            self.mika_brain.start()

            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
    
    def stop_mika(self):
        if self.mika_brain:
            logger.warning("Encerrando processos Mika ...")
            self.mika_brain.stop()
            self.mika_brain.wait()
            self.mika_brain = None

            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            logger.info("Mika em standby")
    
    def reload_mika(self):
        logger.info("Reiniciando cerebro Mika ...")
        self.stop_mika()
        self.start_mika()
    
    def closeEvent(self, event):
        if self.mika_windows:
            self.mika_windows.close()
        self.stop_mika()
        event.accept()

if __name__ == "__main__":
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--enable-gpu-rasterization --ignore-gpu-blocklist --disable-web-security --allow-file-access-from-files"
    )

    app = QApplication(sys.argv)
    dashboard = MikaDashboard()
    dashboard.show()
    sys.exit(app.exec())