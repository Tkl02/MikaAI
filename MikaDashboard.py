import sys
import os
import importlib
import shutil
from pathlib import Path
from PyQt6.QtCore import pyqtSignal, QObject, pyqtSlot, Qt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QPlainTextEdit, QLabel, QDialog, QSlider, QFileDialog)
from PyQt6.QtGui import QTextCursor
from loguru import logger

from mika_core.MikaWindows import MikaWindows
from mika_core import MikaBrain
from mika_core import MacroManager
from mika_core import SystemManager

NEON_MAGENTA = "#ff00ff"
NEON_CYAN = "#00ffff"
NEON_GREEN = "#00ff00"
DARK_BG = "#121212"
PANEL_BG = "#1e1e1e"

BASE_DIR = Path(__file__).resolve().parent

# ==========================================
# POP-UP DE CONFIGURAÇÃO DO VRM
# ==========================================
class VRMConfigDialog(QDialog):
    def __init__(self, mika_windows, parent=None):
        super().__init__(parent)
        self.mika_windows = mika_windows
        self.setWindowTitle("Configurações Visuais da Mika")
        self.resize(350, 450)
        self.setStyleSheet(f"background-color: {PANEL_BG}; color: white; font-family: 'Consolas', monospace;")
        
        layout = QVBoxLayout(self)
        
        config = self.mika_windows.config
        largura = config.get("window_width",300)
        altura = config.get("window_height",400)
        zoom_salvo = int(config.get("camera_zoom",1.0)*10)
        foco_salvo = config.get("camera_focus","head")

        # --- CONTROLES DE TAMANHO DA JANELA ---
        layout.addWidget(QLabel("Largura da Janela:"))
        self.slider_width = QSlider(Qt.Orientation.Horizontal)
        self.slider_width.setRange(200, 1000) # Limites: 200px a 1000px
        self.slider_width.setValue(largura)
        self.slider_width.valueChanged.connect(self.update_size)
        layout.addWidget(self.slider_width)

        layout.addWidget(QLabel("Altura da Janela:"))
        self.slider_height = QSlider(Qt.Orientation.Horizontal)
        self.slider_height.setRange(200, 1000) # Limites: 200px a 1000px
        self.slider_height.setValue(altura)
        self.slider_height.valueChanged.connect(self.update_size)
        layout.addWidget(self.slider_height)

        # --- CONTROLE DE ZOOM ---
        layout.addWidget(QLabel("Zoom da Câmera (FOV):"))
        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(5, 30) 
        self.slider_zoom.setValue(zoom_salvo) # 1.0 (Padrão)
        self.slider_zoom.valueChanged.connect(self.update_zoom)
        layout.addWidget(self.slider_zoom)

        # --- BOTÕES DE FOCO DA CÂMERA ---
        layout.addWidget(QLabel("Foco da Câmera:"))
        cam_layout = QHBoxLayout()

        
        self.btn_head = QPushButton("Rosto")
        self.btn_torso = QPushButton("Torso")
        self.btn_full = QPushButton("Corpo Inteiro")
        
        # Conecta os botões enviando a si mesmos para gerenciar o CSS dinâmico
        self.btn_head.clicked.connect(lambda: self.set_focus('head', self.btn_head))
        self.btn_torso.clicked.connect(lambda: self.set_focus('torso', self.btn_torso))
        self.btn_full.clicked.connect(lambda: self.set_focus('fullbody', self.btn_full))
        
        for btn in [self.btn_head, self.btn_torso, self.btn_full]:
            btn.setStyleSheet(self.get_btn_style(active=False))
            cam_layout.addWidget(btn)
            
        layout.addLayout(cam_layout)

        if foco_salvo == "head": self.set_focus('head',self.btn_head)
        elif foco_salvo == "torso": self.set_focus('torso',self.btn_torso)
        elif foco_salvo == "fullbody": self.set_focus('fullbody',self.btn_full)
        
        # O rosto é o padrão ativo ao abrir
        layout.addSpacing(20)

        # --- SELETOR DE AVATAR (SUBSTITUIÇÃO FÍSICA) ---
        self.btn_load_vrm = QPushButton("CARREGAR NOVO AVATAR (.vrm)")
        self.btn_load_vrm.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {NEON_MAGENTA}; border: 2px solid {NEON_MAGENTA}; padding: 10px; font-weight: bold; border-radius: 5px; }}
            QPushButton:hover {{ background-color: {NEON_MAGENTA}; color: black; }}
        """)
        self.btn_load_vrm.clicked.connect(self.replace_vrm_file)
        layout.addWidget(self.btn_load_vrm)

    def get_btn_style(self, active):
        """Retorna o CSS dinâmico: Brilha se ativo, invisível/clicável se inativo"""
        if active:
            return f"background-color: transparent; color: {NEON_CYAN}; border: 2px solid {NEON_CYAN}; padding: 5px; font-weight: bold; border-radius: 3px;"
        return f"background-color: transparent; color: white; border: 1px solid #444; padding: 5px; border-radius: 3px;"

    def update_size(self):
        if self.mika_windows:
            self.mika_windows.update_window_size(self.slider_width.value(), self.slider_height.value())

    def update_zoom(self):
        if self.mika_windows:
            # Converte o inteiro (15) para float (1.5)
            zoom_val = self.slider_zoom.value() / 10.0
            self.mika_windows.set_camera_zoom(zoom_val)

    def set_focus(self, focus_type, active_btn):
        if self.mika_windows:
            self.mika_windows.set_camera_focus(focus_type)
        
        # Reseta todos e ativa apenas o clicado
        for btn in [self.btn_head, self.btn_torso, self.btn_full]:
            btn.setEnabled(True)
            btn.setStyleSheet(self.get_btn_style(active=False))
            
        active_btn.setEnabled(False) # Trava o botão
        active_btn.setStyleSheet(self.get_btn_style(active=True)) # Aplica o neon

    def replace_vrm_file(self):
        """Abre o seletor, substitui o arquivo Mika-0.vrm antigo pelo novo e recarrega"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecione o novo Avatar VRM", "", "VRM Files (*.vrm)")
        if file_path:
            target_path = BASE_DIR / "mika_core" / "Mika-0.vrm" # Ajuste o caminho conforme a estrutura da sua pasta
            try:
                # Substitui fisicamente o arquivo
                shutil.copy2(file_path, target_path)
                logger.info(f"Avatar substituído com sucesso! Arquivo novo copiado de: {file_path}")
                
                if self.mika_windows:
                    self.mika_windows.load_vrm_viewer() # Recarrega limpando a GPU
            except Exception as e:
                logger.error(f"Erro ao substituir o avatar: {e}")

# ==========================================
# CÓDIGO ORIGINAL DO DASHBOARD
# ==========================================
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
        self.resize(900, 500)
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

        self.btn_mode = QPushButton("MODE: F9 (manual)")
        self.style_button(self.btn_mode, NEON_CYAN)
        self.btn_mode.clicked.connect(self.toggle_mode)
        control_panel.addWidget(self.btn_mode)

        self.btn_vrm_toggle = QPushButton("VRM: MOSTRAR/ESCONDER")
        self.style_button(self.btn_vrm_toggle, NEON_MAGENTA)
        self.btn_vrm_toggle.clicked.connect(self.toggle_vrm_window)
        control_panel.addWidget(self.btn_vrm_toggle)

        # --- NOVO BOTÃO: ABRE AS CONFIGURAÇÕES VISUAIS ---
        self.btn_config = QPushButton("⚙️ CONFIGURAÇÕES VRM")
        self.style_button(self.btn_config, NEON_CYAN)
        self.btn_config.clicked.connect(self.open_vrm_config)
        control_panel.addWidget(self.btn_config)

        control_panel.addStretch()
        layout.addLayout(control_panel, 1)

        terminal_layout = QVBoxLayout()
        terminal_label = QLabel("SYSTEM LOGS")
        terminal_label.setStyleSheet(f"color: {NEON_MAGENTA}; font-weight: bold;")
        terminal_layout.addWidget(terminal_label)

        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setStyleSheet(f"background-color: #000000; color: #00ff00; border: 1px solid {NEON_CYAN}; font-size: 12px")
        terminal_layout.addWidget(self.terminal)
        layout.addLayout(terminal_layout, 2)

    def style_button(self, btn, color):
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: {color}; border: 2px solid {color}; padding: 15px; font-weight: bold; font-size: 14px; border-radius: 5px; }}
            QPushButton:hover {{ background-color: {color}; color: black; }}
            QPushButton:disabled {{ border-color: #444; color: #444; }}
        """)
        
    @pyqtSlot(str)
    def update_terminal(self, message):
        self.terminal.appendPlainText(message.strip())
        self.terminal.moveCursor(QTextCursor.MoveOperation.End)
    
    def open_vrm_config(self):
        """Abre o pop-up de configuração e passa a referência da janela 3D"""
        if not self.mika_windows or self.mika_windows.isHidden():
            logger.warning("Abra a interface VRM primeiro para configurar!")
            return
        
        dialog = VRMConfigDialog(self.mika_windows, self)
        dialog.exec() # Abre em modo modal (trava o dashboard enquanto aberto)

    def toggle_vrm_window(self):
        if not self.mika_windows or self.mika_windows.isHidden():
            logger.info("Dashboard: Abrindo e recarregando interface VRM...")
            if not self.mika_windows:
                self.mika_windows = MikaWindows()
                if self.mika_brain:
                    self.mika_brain.change_anim.connect(self.mika_windows.update_expression)
                    self.mika_brain.change_talking_state.connect(self.mika_windows.set_talking)
                    self.mika_windows.brain = self.mika_brain
            self.mika_windows.show()
            self.mika_windows.load_vrm_viewer() 
        else:
            logger.info("Dashboard: Escondendo janela VRM.")
            self.mika_windows.hide()

    def start_mika(self):
        if not self.mika_windows:
            logger.info("Iniciando Interface VRM ...")
            self.mika_windows = MikaWindows()
            self.mika_windows.show()
        elif self.mika_windows.isHidden():
            self.mika_windows.show()
    
        if not self.mika_brain:
            logger.info("Iniciando cerebro da Mika ...")
            importlib.reload(MikaBrain)
            importlib.reload(SystemManager)
            importlib.reload(MacroManager)
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
        
        if self.mika_brain:
            self.mika_brain.set_activation_mode("manual")
            
        self.btn_mode.setText("MODE: F9 (manual)")
        self.style_button(self.btn_mode, NEON_CYAN)
        logger.info("Dashboard: Ativação por voz resetada para modo manual.")
    
    def closeEvent(self, event):
        if self.mika_windows:
            self.mika_windows.close()
        self.stop_mika()
        event.accept()

    def toggle_mode(self):
        if not self.mika_brain: return

        if self.mika_brain.active_mode == "manual":
            self.mika_brain.set_activation_mode("voice")
            self.btn_mode.setText("Modo de voz ativo")
            self.style_button(self.btn_mode, NEON_CYAN)
            logger.info("Dashoboard: Ativação por voz ligado")
        else:
            self.mika_brain.set_activation_mode("manual")
            self.btn_mode.setText("Modo de voz desativado")
            self.style_button(self.btn_mode, NEON_CYAN)
            logger.info("Dashboard: Ativação por voz desativada")

if __name__ == "__main__":
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--enable-gpu-rasterization --ignore-gpu-blocklist --disable-web-security --allow-file-access-from-files"
    )

    app = QApplication(sys.argv)
    dashboard = MikaDashboard()
    dashboard.show()
    sys.exit(app.exec())