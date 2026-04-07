import sounddevice as sd
import numpy as np 
import scipy.io.wavfile as wav
import asyncio
import os
import sys
import tempfile
import warnings
from pathlib import Path
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
import edge_tts
import pygame
from dotenv import load_dotenv
from loguru import logger
from faster_whisper import WhisperModel
from groq import Groq
from pymongo import MongoClient
from pynput import keyboard

load_dotenv()

# Carregar variáveis de ambiente (opcional)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
BASE_DIR = Path(__file__).resolve().parent
VRM_FILE = BASE_DIR / "BaseModel.vrm"
INDEX_FILE = BASE_DIR / "index.html"


def init_audio_mixer() -> bool:
    """Inicializa o mixer e retorna se o áudio está disponível."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            pygame.mixer.init()
        return True
    except Exception as e:
        logger.error(f"Erro ao inicializar mixer: {e}")
        return False


AUDIO_AVAILABLE = init_audio_mixer()

class MikaBrain(QThread):
    change_anim = pyqtSignal(str)
    finished_speaking = pyqtSignal()

    def __init__(self, windows_ref):
        super().__init__()
        self.window = windows_ref
        self.client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
        self.stt_model = None
        try:
            self.stt_model = WhisperModel("base", device="cpu", compute_type="int8")
        except Exception as exc:
            logger.warning(f"Falha ao inicializar o modelo Whisper: {exc}")

        self.mongo = None
        if MONGO_URI:
            try:
                self.mongo = MongoClient(MONGO_URI)["MikaDB"]["history"]
            except Exception as exc:
                logger.warning(f"Falha ao conectar no MongoDB: {exc}")
        self.audio_available = AUDIO_AVAILABLE

        self.recording = []
        self.is_recording = False
        self.fs = 16000
    
    def run(self):
        logger.info("MikaBrain Ativo. Aguardando Hotkey...")
        self.start_hotkey_listener()
    
    def start_hotkey_listener(self):
        target_vk = 268964265

        def on_press(key):
            if hasattr(key, "vk") and key.vk == target_vk:
                if not self.is_recording:
                    logger.info("Mika ouvindo ...")
                    self.is_recording = True
                    self.recording = []
                    self.change_anim.emit("happy")
                    self.stream = sd.InputStream(samplerate=self.fs, channels=1, callback=self.audio_callback)
                    self.steam.start()
        
        def on_release(key):
            if hasattr(key, "vk") and key.vk == target_vk:
                if self.is_recording:
                    logger.info("Mika Processando audio ...")
                    self.is_recording = False
                    self.stream.stop()
                    self.stream.close()

                    audio_data = np.concatenate(self.recording)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                        wav.write(f.name, self.fs, audio_data)
                        audio_path = f.name
                    
                    asyncio.run(self.process_full_cycle(audio_path))


        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    
    def audio_callback(self, indata,frames,time,status):
        if self.is_recording:
            self.recording.append(indata.copy())
    
    async def process_full_cycle(self, audio_path):
        segments, _ = self.stt_model.transcribe(audio_path)
        user_text = "".join([s.text for s in segments])
        logger.info(f"usuario disse: {user_text}")

        os.unlink(audio_path)

        if user_text.strip():
            await self.think_and_speak(user_text)
    
    async def think_and_speak(self, text_input: str):
        if not self.client:
            logger.error("GROQ_API_KEY não definido. Defina a variável de ambiente para habilitar respostas da IA.")
            return

        chat_compilation = self.client.chat.completions.create(
            messages=[{"role": "system", "content": "Voce é a Mika, assistente de desktop Linux"},
                      {"role": "user", "content": text_input},
                      ],
                      model="llama3-8b-8192"
        )
        response = chat_compilation.choices[0].message.content

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            temp_audio_path = Path(temp_audio.name)

        communicate = edge_tts.Communicate(response, "pt-BR-FranciscaNeural")
        await communicate.save(str(temp_audio_path))

        if not self.audio_available:
            logger.warning("Áudio indisponível no ambiente atual. Resposta gerada sem reprodução.")
            return

        try:
            pygame.mixer.music.load(str(temp_audio_path))
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                self.window.browser.page().runJavaScript(
                    "if(window.changeMikaExpression) changeMikaExpression('happy');"
                )
                await asyncio.sleep(0.2)
        finally:
            if temp_audio_path.exists():
                temp_audio_path.unlink(missing_ok=True)

class MemoryManager:
    """Gerencia a memória e contexto do usuário no MongoDB"""

    def __init__(self):
        self.client = None
        self.collection = None
        mongo_url = os.getenv("MONGO_URI", MONGO_URI)
        if mongo_url:
            try:
                self.client = MongoClient(mongo_url)
                self.db = self.client["mika_ai"]
                self.collection = self.db["user_context"]
            except Exception as exc:
                logger.warning(f"MongoDB indisponível: {exc}")

    def save_preference(self, key: str, value):
        """Salva uma preferência do usuário"""
        if not self.collection:
            logger.warning("Contexto do usuário não salvo porque o MongoDB não está disponível.")
            return

        try:
            self.collection.update_one(
                {"user_id": "default"},
                {"$set": {f"preferences.{key}": value}},
                upsert=True
            )
            logger.info(f"Preferência salva: {key} = {value}")
        except Exception as e:
            logger.error(f"Erro ao salvar preferência: {e}")

    def get_context(self):
        """Recupera o contexto do usuário"""
        if not self.collection:
            return None

        try:
            return self.collection.find_one({"user_id": "default"})
        except Exception as e:
            logger.error(f"Erro ao recuperar contexto: {e}")
            return None


class MikaVoice:
    """Gerencia a geração e reprodução de áudio da Mika"""
    
    def __init__(self):
        self.voice = "pt-BR-FranciscaNeural"
        self.response_file = Path("response.mp3")
        self.audio_available = AUDIO_AVAILABLE
        if self.audio_available:
            logger.info("Mixer de áudio inicializado")
    
    async def speak(self, text: str, windows_ref=None):
        """Gera e reproduz áudio usando edge-tts"""
        if not self.audio_available:
            logger.warning("Áudio indisponível: resposta em voz desativada.")
            return

        try:
            logger.info(f"Gerando áudio: {text}")
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(self.response_file))
            
            if self.response_file.exists():
                pygame.mixer.music.load(str(self.response_file))
                pygame.mixer.music.play()
                logger.info("Áudio reproduzido com sucesso")
            else:
                logger.error("Arquivo de áudio não foi criado")
        except Exception as e:
            logger.error(f"Erro ao reproduzir áudio: {e}")


class AIAgentWorker(QThread):
    """Worker que executa a lógica da IA em thread separada"""
    
    change_animation = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.stop_signal = False

    def run(self):
        logger.info("MikaAI: Motor de lógica iniciado...")
        while not self.stop_signal:
            self.msleep(5000)
        logger.info("Worker parado")

    def stop(self):
        """Para a execução do worker"""
        self.stop_signal = True


class MikaWindows(QMainWindow):
    """Janela principal da aplicação com renderização VRM"""
    
    def __init__(self):
        super().__init__()
        self.voice_manager = MikaVoice()
        self.memory_manager = MemoryManager()
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
        event.accept()


if __name__ == "__main__":
    os.environ["QT_QPA_PLATFORM"] = "wayland"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--enable-gpu-rasterization --ignore-gpu-blocklist --disable-web-security"
    )

    print(GROQ_API_KEY)
    print(MONGO_URI)  
    
    app = QApplication(sys.argv)

    mika_windows = MikaWindows()
    mika_windows.show()
    brain = MikaBrain(mika_windows)
    brain.change_anim.connect(mika_windows.update_expression)
    brain.start()

    worker = AIAgentWorker()
    worker.change_animation.connect(mika_windows.update_expression)
    worker.start()

    app.aboutToQuit.connect(worker.stop)

    sys.exit(app.exec())