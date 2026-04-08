from PyQt6.QtCore import QThread, pyqtSignal
from LocalMemoryManager import LocalMemoryManager
from groq import Groq
from dotenv import load_dotenv
import os
from faster_whisper import WhisperModel
from loguru import logger
import pygame
import selectors
from MikaVoice import AUDIO_AVAILABLE
import asyncio
import numpy as np 
from evdev import InputDevice, ecodes,categorize
import sounddevice as sd
import scipy.io.wavfile as wav
import threading
import edge_tts

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class MikaBrain(QThread):
    change_anim = pyqtSignal(str)
    finished_speaking = pyqtSignal()

    def __init__(self, windows_ref):
        super().__init__()
        self._run_flag = True
        self.window = windows_ref
        self.memory = LocalMemoryManager()
        self.client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
        self.device_path = '/dev/input/event4'
        self.stt_model = None
        self.audio_available = AUDIO_AVAILABLE
        self.recording_data = []
        self.is_recording = False
        self.is_speacking = False
        self.fs = 16000
        self.system_prompt = self.load_context_file()

        try:
            self.stt_model = WhisperModel("base", device="cpu", compute_type="int8")
            logger.info(f"Whisper carregado com sucesso")
        except Exception as exc:
            logger.warning(f"Falha ao inicializar o modelo Whisper: {exc}")
        
    def load_context_file(self):
        try:
            with open("context.txt", "r") as f:
                context = f.read().strip()
                return context
        except Exception as erro:
            logger.error(f"Erro na leitura do context")

    
    def run(self):
        logger.info("MikaBrain Ativo. Aguardando Hotkey...")
        self.listen_evdev()
    
    def stop(self):
        self._run_flag = False
    
    def stop_mika_voice(self):
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            self.is_speacking = False
            logger.info("Mika: Foi interrompida")
    
    def listen_evdev(self):
        try:
            device = InputDevice(self.device_path)
            selector = selectors.DefaultSelector()
            selector.register(device, selectors.EVENT_READ)

            while self._run_flag:
                for key, mask in selector.select(timeout=0.5):
                    for event in device.read():
                        if event.type == ecodes.EV_KEY:
                            key_event = categorize(event)
                            if key_event.keycode == 'KEY_PRESENTATION':
                                self.handle_key(key_event)
            
            device.close() # Libera o dispositivo
            logger.info("Dispositivo evdev liberado.")
        except Exception as e:
            logger.error(f"Erro no evdev: {e}")

    def handle_key(self, key_event):
        """Lógica de pressão e soltura separada para clareza"""
        if key_event.keystate == 1:

            self.stop_mika_voice()
            logger.info("Mika: Gravando...")
            self.is_recording = True
            self.recording_data = []
            self.stream = sd.InputStream(samplerate=self.fs, channels=1, callback=self.audio_callback)
            self.stream.start()

        elif key_event.keystate == 0:
            logger.info("Mika: Processando...")
            self.is_recording = False
            if hasattr(self, 'stream'):
                self.stream.stop()
                self.stream.close()
            
            if self.recording_data:
                audio_full = np.concatenate(self.recording_data)
                temp_wav = "user_voice.wav"
                wav.write(temp_wav, self.fs, audio_full)
                threading.Thread(target=lambda: asyncio.run(self.process_full_cycle(temp_wav)), daemon=True).start()
    
    def audio_callback(self, indata,frames,time,status):
        if self.is_recording:
            self.recording_data.append(indata.copy())
    
    async def process_full_cycle(self, audio_path):
        try:
            segments, info = self.stt_model.transcribe(
                 audio_path,
                 language="pt",
                 beam_size=5,
                 condition_on_previous_text=False
            )
            user_text = " ".join([s.text for s in segments]).strip()

            if len(user_text) < 2:
                logger.warning("Audio muito curto ou ruido detectado")
                return

            logger.info(f"Voce disse: {user_text}")
            await self.think_and_speak(user_text)

            
            
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as erro:
            logger.error(f"Erro no ciclo AI: {erro}")
    
    async def think_and_speak(self, text_input: str):
        # Use o modelo atualizado que não está desativado
        MODELO_ATUAL = "llama-3.1-8b-instant" 
        
        try:
            chat_compilation = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text_input},
                ],
                model=MODELO_ATUAL
            )
            response = chat_compilation.choices[0].message.content
            logger.info(f"Mika respondeu: {response}")

            # Geração do Áudio
            communicate = edge_tts.Communicate(response, "pt-BR-FranciscaNeural")
            temp_file = "temp_res.mp3"
            await communicate.save(temp_file)

            # Reprodução
            if os.path.exists(temp_file):
                pygame.mixer.music.load(temp_file)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    if not self.is_speacking:
                        break
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Erro no ciclo de pensamento: {e}")
        finally:
            self.is_speacking = False

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