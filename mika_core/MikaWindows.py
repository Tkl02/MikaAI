from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
from mika_core.LocalMemoryManager import LocalMemoryManager
from loguru import logger
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

class MikaWindows(QMainWindow):
    # classe que mostra a janela do VRM da mika simulando um "webBrowser"
    def __init__(self):
        super().__init__()
        self.memory_manager = LocalMemoryManager()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Mika AI")
        self.setFixedSize(300, 400)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )

        self.central_Widget = QWidget()
        self.layout = QVBoxLayout(self.central_Widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.central_Widget)

        self.browser = QWebEngineView()
        self.browser.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.layout.addWidget(self.browser)

        logger.info("Janela da Mika pronta e aguardando renderização")
        self.browser.setUrl(QUrl.fromLocalFile(str(INDEX_FILE)))
    
    def update_vrm(self, expression):
        self.browser.page().runJavaScript(f"changeMikaExpression('{expression}');")
    
    def update_expression(self, state):
        js_code = f"changeMikaExpression('{state}');"
        self.browser.page().runJavaScript(js_code)
        logger.info(f"Comando enviado ao VRM: {state}")
    
    def set_talking(self, is_talking: bool):
        if is_talking:
            self.browser.page().runJavaScript("startTalking();")
        else:
            self.browser.page().runJavaScript("stopTalking();")
    
    def load_vrm_viewer(self):
        self.browser.setUrl(QUrl.fromLocalFile(str(INDEX_FILE)))

    def closeEvent(self, event):
        """Apenas fecha a janela de forma segura, sem derrubar o Dashboard."""
        logger.info("Janela VRM fechada de forma segura.")
        event.accept()