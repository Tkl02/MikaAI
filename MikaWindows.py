from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
from MikaVoice import MikaVoice
from LocalMemoryManager import LocalMemoryManager
from loguru import logger
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

class MikaWindows(QMainWindow):
    """Janela principal da aplicação com renderização VRM"""

    def __init__(self):
        super().__init__()
        self.voice_manager = MikaVoice()
        self.memory_manager = LocalMemoryManager()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Mika AI")
        self.setFixedSize(300, 400)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        )

        # Container principal
        self.central_Widget = QWidget()
        self.layout = QVBoxLayout(self.central_Widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.central_Widget)

        # Renderizar o VRM via three.js
        self.browser = QWebEngineView()
        self.browser.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.layout.addWidget(self.browser)

        logger.info("Janela da Mika pronta e aguardando renderização")
        self.browser.setUrl(QUrl.fromLocalFile(str(INDEX_FILE)))
    
    def update_vrm(self, expression):
        self.browser.page().runJavaScript(f"changeMikaExpression('{expression}');")
    
    def update_expression(self, state):
        """Atualiza a expressão da Mika no VRM"""
        js_code = f"changeMikaExpression('{state}');"
        self.browser.page().runJavaScript(js_code)
        logger.info(f"Comando enviado ao VRM: {state}")
    
    def load_vrm_viewer(self):
        """Carrega o visualizador VRM"""
        self.browser.setUrl(QUrl.fromLocalFile(str(INDEX_FILE)))

    def closeEvent(self, event):
        """Limpa recursos ao fechar a janela"""
        logger.info("Encerrando aplicação")
        if hasattr(self, 'brain'):
            self.brain.stop()
        QApplication.quit()
        self.event.accept()