import json
from PyQt6.QtCore import Qt, QUrl, QSettings, QPoint, QEvent
from PyQt6.QtWidgets import QMainWindow,QVBoxLayout,QWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QMouseEvent
from mika_core.LocalMemoryManager import LocalMemoryManager
from loguru import logger
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
CONFIG_FILE = BASE_DIR / "mika_window_config.json"

class MikaWindows(QMainWindow):
    def __init__(self):
        super().__init__()
        self.memory_manager = LocalMemoryManager()
        self.settings = QSettings("MikaAI","MikaAgent")
        self.config = self.load_config()
        self._drag_start_global = None
        self._window_start_pos = QPoint()
        self._is_dragging = False
        self._drag_filter_targets = set()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Mika AI")

        largura = self.config.get("window_width",300)
        altura = self.config.get("window_height",400)
        pos_x = self.config.get("window_x",100)
        pos_y = self.config.get("window_y",100)

        self.resize(largura,altura)
        self.move(pos_x,pos_y)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )

        self.central_Widget = QWidget()
        self.central_Widget.setStyleSheet("background: transparent;")
        
        self.layout = QVBoxLayout(self.central_Widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.central_Widget)

        self.browser = QWebEngineView()
        
        self.browser.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.browser.setStyleSheet("background: transparent;")
        self.browser.page().setBackgroundColor(Qt.GlobalColor.transparent)
        
        self.layout.addWidget(self.browser)
        self._setup_drag_event_filters()

        logger.info("Janela da Mika pronta e aguardando renderização")
        self.browser.loadFinished.connect(self.apply_saved_camera_settings)
        self.browser.setUrl(QUrl.fromLocalFile(str(INDEX_FILE)))
    
    def apply_saved_camera_settings(self):
        zoom = self.config.get("camera_zoom",1.0)
        foco = self.config.get("camera_focus", "head")
        self.set_camera_zoom(zoom)
        self.set_camera_focus(foco)
        self._setup_drag_event_filters()
        logger.info(f"Mikawindow: Configuração de camera aplicada")

    def _register_drag_filter(self, widget):
        if not widget:
            return
        widget_id = id(widget)
        if widget_id in self._drag_filter_targets:
            return
        widget.installEventFilter(self)
        self._drag_filter_targets.add(widget_id)

    def _setup_drag_event_filters(self):
        self._register_drag_filter(self)
        self._register_drag_filter(self.central_Widget)
        self._register_drag_filter(self.browser)
        for child in self.browser.findChildren(QWidget):
            self._register_drag_filter(child)

    def _save_window_position(self):
        self.config["window_x"] = self.pos().x()
        self.config["window_y"] = self.pos().y()
        self.save_config()
        logger.info(f"MikaWindows: Nova posição salva: {self.pos().x()}, {self.pos().y()}")

    def _handle_drag_event(self, event: QMouseEvent):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_global = event.globalPosition().toPoint()
            self._window_start_pos = self.pos()
            self._is_dragging = False
            return False

        if event.type() == QEvent.Type.MouseMove and self._drag_start_global is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            delta = event.globalPosition().toPoint() - self._drag_start_global
            if not self._is_dragging and delta.manhattanLength() >= 3:
                self._is_dragging = True
            if self._is_dragging:
                self.move(self._window_start_pos + delta)
                return True
            return False

        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._is_dragging
            self._drag_start_global = None
            self._is_dragging = False
            if was_dragging:
                self._save_window_position()
                return True
        return False

    def eventFilter(self, source, event):
        if isinstance(source, QWidget) and (source is self or self.isAncestorOf(source)):
            if event.type() in {
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseMove,
                QEvent.Type.MouseButtonRelease,
            }:
                if self._handle_drag_event(event):
                    return True
        return super().eventFilter(source, event)

    def load_config(self):
        default_config = {
            "window_width":300,
            "window_height":400,
            "window_x":100,
            "window_y":100,
            "camera_zoom": 1.0,
            "camera_focus": "head"
            }
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return {**default_config, **json.load(f)} 
        except Exception as erro:
            logger.error(f"Mikawindows: Erro ao ler config.json: {erro}")
        return default_config
    
    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config,f,indent=4)
        except Exception as e:
            logger.error(f"Mikawindow: Erro ao salvar config: {e}")


    def mousePressEvent(self, event: QMouseEvent):
        if self._handle_drag_event(event):
            return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self._handle_drag_event(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._handle_drag_event(event):
            return
        super().mouseReleaseEvent(event)

    def update_window_size(self, width: int, height: int):
        self.resize(width, height)
        self.config["window_width"] = width
        self.config["window_height"] = height
        self.save_config()
        logger.info(f"Mikaindows: proporção salva {width}x{height}.")
    
    def set_camera_focus(self, focus_type:str):
        self.browser.page().runJavaScript(f"if (typeof setCameraFocus !== 'undefined') setCameraFocus('{focus_type}');")
        self.config["camera_focus"] = focus_type
        self.save_config()

    def set_camera_zoom(self, zoom_multiplier: float):
        self.browser.page().runJavaScript(f"if (typeof setZoom !== 'undefined') setZoom({zoom_multiplier});")
        self.config["camera_zoom"] = zoom_multiplier
        self.save_config()
    
    def update_expression(self, state):
        js_code = f"if (typeof changeMikaExpression !== 'undefined') changeMikaExpression('{state}');"
        self.browser.page().runJavaScript(js_code)
        logger.info(f"Comando enviado ao vrm: {state}")
    
    def set_talking(self, is_talking: bool):
        if is_talking:
            self.browser.page().runJavaScript("if (typeof startTalking !== 'undefined') startTalking();")
        else:
            self.browser.page().runJavaScript("if (typeof stopTalking !== 'undefined') stopTalking();")
    
    def load_vrm_viewer(self):
        logger.info("Recarregando visualizador VRM")
        self.browser.setUrl(QUrl.fromLocalFile(str(INDEX_FILE)))
    
    def closeEvent(self, event):
        logger.info("Janela VRM fechada de forma segura")
        event.accept()