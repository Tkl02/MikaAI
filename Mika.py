import os
import sys
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication
from dotenv import load_dotenv
from loguru import logger
from MikaBrain import MikaBrain, AIAgentWorker
from MikaWindows import MikaWindows

load_dotenv()

# Carregar variáveis de ambiente (opcional)
BASE_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    os.environ["QT_QPA_PLATFORM"] = "wayland"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--enable-gpu-rasterization --ignore-gpu-blocklist --disable-web-security"
    )
    
    app = QApplication(sys.argv)

    mika_windows = MikaWindows()
    mika_windows.show()
    brain = MikaBrain(mika_windows)
    brain.change_anim.connect(mika_windows.update_expression)
    mika_windows.brain = brain
    brain.start()

    worker = AIAgentWorker()
    worker.change_animation.connect(mika_windows.update_expression)
    worker.start()

    app.aboutToQuit.connect(worker.stop)

    sys.exit(app.exec())