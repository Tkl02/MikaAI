from PyQt6.QtCore import QThread, pyqtSignal
from LocalMemoryManager import LocalMemoryManager
from groq import Groq
from dotenv import load_dotenv
import uuid
import os
from loguru import logger
import shlex
import pygame
from MikaVoice import AUDIO_AVAILABLE
import asyncio
import numpy as np 
import sounddevice as sd
import scipy.io.wavfile as wav
import threading
import edge_tts
import keyboard 
import re
import subprocess
from pathlib import Path
import time
from AppOpener import open as open_app

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
        self.audio_available = AUDIO_AVAILABLE
        self.recording_data = []
        self.is_recording = False
        self.is_speaking = False
        self.fs = 16000
        self.system_prompt = self.load_context_file()
        self.comando_pendente = None
        
        # Gerenciamento de diretório temporário
        self.temp_dir = Path(__file__).resolve().parent / "temp_audio"
        self.ensure_temp_dir()
        self.cleanup_temp_files()
        
        logger.info("MikaBrain inicializado com sucesso (Groq Mode)")
        
    def load_context_file(self):
        try:
            with open("context.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as erro:
            logger.error(f"Erro na leitura do context: {erro}")
            return ""
    
    def ensure_temp_dir(self):
        if not self.temp_dir.exists():
            self.temp_dir.mkdir(parents=True, exist_ok=True)

    def cleanup_temp_files(self):
        try:
            for file in self.temp_dir.glob("*"):
                if file.is_file():
                    try:
                        os.remove(file)
                    except:
                        pass 
            logger.info("Cache de áudio limpo.")
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")

    def run(self):
        logger.info("MikaBrain Ativo. Aguardando F9...")
        self.listen_windows()
    
    def stop(self):
        self._run_flag = False
    
    def stop_mika_voice(self):
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            self.is_speaking = False
            logger.info("Mika: Áudio interrompido")
    
    def listen_windows(self):
        try:
            keyboard.on_press_key('F9', self.handle_key_press)
            keyboard.on_release_key('F9', self.handle_key_release)
            while self._run_flag:
                self.msleep(100)
        except Exception as e:
            logger.error(f"Erro no teclado: {e}")

    def handle_key_press(self, event):
        if not self.is_recording:
            self.stop_mika_voice()
            logger.info("Mika: Escutando...")
            self.is_recording = True
            self.recording_data = []
            self.stream = sd.InputStream(samplerate=self.fs, channels=1, callback=self.audio_callback)
            self.stream.start()

    def audio_callback(self, indata, frames, time, status):
        if self.is_recording:
            self.recording_data.append(indata.copy())
    
    def handle_key_release(self, event):
        if self.is_recording:
            logger.info("Mika: Processando voz...")
            self.is_recording = False
            if hasattr(self, 'stream'):
                self.stream.stop()
                self.stream.close()
            
            if self.recording_data:
                audio_full = np.concatenate(self.recording_data)
                temp_wav = self.temp_dir / f"user_{uuid.uuid4().hex[:8]}.wav"
                wav.write(str(temp_wav), self.fs, audio_full)
                
                threading.Thread(
                    target=lambda f=str(temp_wav): asyncio.run(self.process_full_cycle(f)), 
                    daemon=True
                ).start()
    
    async def process_full_cycle(self, audio_path):
        try:
            with open(audio_path, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=(audio_path, file.read()),
                    model="whisper-large-v3",
                    language="pt",
                    response_format="text"
                )
            
            user_text = transcription.strip()
            if len(user_text) < 2: return

            logger.info(f"Você: {user_text}")
            await self.think_and_speak(user_text)
            self.safe_delete(audio_path)

        except Exception as e:
            logger.error(f"Erro no ciclo de voz: {e}")
    
    def safe_delete(self, file_path):
        for _ in range(5):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                return
            except:
                time.sleep(0.2)
    
    def abrir_aplicativo(self, app_name):
        app_name_lower = app_name.lower()
        logger.info(f"Abrindo app: {app_name_lower}")
        try:
            open_app(app_name_lower, match_closest=True)
            logger.info(f"Sinal de abertura enviado: {app_name_lower}")
        except Exception as e:
            logger.error(f"Erro na abertura do app: '{app_name_lower}' erro: {e}")

    async def think_and_speak(self, text_input: str):
        MODELO_ATUAL = "llama-3.1-8b-instant" 
        
        if self.comando_pendente:
            confirmation = ["sim", "certeza", "pode", "ok", "manda ver", "confirmo"]
            if any(p in text_input.lower() for p in confirmation):
                self.exec_command_powershell(self.comando_pendente)
                text_input = f"(O comando {self.comando_pendente} foi executado. Confirme para mim)."
            else:
                text_input = "(O comando foi cancelado pelo usuário)."
            self.comando_pendente = None
                
        try:
            messages_list = [{"role": "system", "content": self.system_prompt}]
            lembramcas = self.memory.search_memory(text_input, n_results=2)

            if lembramcas:
                contexto_passado = "\n".join(lembramcas)
                msg_contexto = f"[LEMBRAÇAS RELEVANTES DO PASSADO]:\n{contexto_passado}\nUser essa lembramças se forem uteis para o contexto atual"
                messages_list.append({"role":"system","content":msg_contexto})
                logger.info("Memoria antega resgatada e injetada no prompt")

            for interacao in self.memory.short_term_memory:
                if isinstance(interacao, dict):
                    messages_list.append({"role": "user", "content": interacao["user"]})
                    messages_list.append({"role": "assistant", "content": interacao["mika"]})
            
            messages_list.append({"role": "user", "content": text_input})
            
            chat_compilation = self.client.chat.completions.create(
                messages=messages_list,
                model=MODELO_ATUAL
            )
            response = chat_compilation.choices[0].message.content
            
            # Regex robusto para capturar comandos (incluindo quebras de linha)
            command_match = re.search(r'\[\[EXEC:\s*(.+?)\]\]', response, re.DOTALL)
            open_match = re.search(r'\[\[OPEN:\s*(.+?)\]\]', response, re.DOTALL)
            
            command_to_exec = None
            app_to_open = None

            if command_match:
                command_raw = command_match.group(1).strip()
                cmd_base = command_raw.split()[0].lower() if command_raw else ""
                response = re.sub(r'\[\[EXEC:\s*.+?\]\]', '', response, flags=re.DOTALL).strip()

                if cmd_base in ["remove-item", "rm", "del", "rmdir"]:
                    self.comando_pendente = command_raw
                    response += " Notei que isso vai apagar arquivos. Tem certeza?"
                else:
                    command_to_exec = command_raw
            
            if open_match:
                app_to_open = open_match.group(1).strip()
                response = re.sub(r'\[\[OPEN:\s*.+?\]\]', '', response, flags=re.DOTALL).strip()

            logger.info(f"Mika: {response}")
            self.memory.add_history(text_input, response)

            # Geração de áudio com correção de tipo (Path object)
            temp_res = self.temp_dir / f"mika_{uuid.uuid4().hex[:8]}.mp3"
            communicate = edge_tts.Communicate(response, "pt-BR-FranciscaNeural")
            await communicate.save(str(temp_res))

            if temp_res.exists():
                pygame.mixer.music.load(str(temp_res))
                pygame.mixer.music.play()
                self.is_speaking = True
                self.change_anim.emit("happy") # Ativa animação

                if command_to_exec:
                    self.exec_command_powershell(command_to_exec)
                
                if app_to_open:
                    self.abrir_aplicativo(app_to_open)
                
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)

                pygame.mixer.music.unload()
                self.change_anim.emit("neutral") # Volta ao normal
                self.safe_delete(str(temp_res))

        except Exception as e:
            logger.error(f"Erro no pensamento: {e}")
        finally:
            self.is_speaking = False

    def exec_command_powershell(self, command):
        if not command:
            return

        try:
            parts = shlex.split(command, posix=False)
        except Exception:
            parts = command.split()

        cmd_base = parts[0].lower()

        # normaliza aliases comuns do PowerShell
        aliases = {
            "ls": "get-childitem",
            "dir": "get-childitem",
            "mkdir": "new-item",
            "rm": "remove-item",
            "del": "remove-item",
            "echo": "write-output",
            "cd": "set-location",
            "start": "start-process"
        }

        cmd_base = aliases.get(cmd_base, cmd_base)

        allowed = {
            "new-item",
            "get-childitem",
            "remove-item",
            "set-location",
            "write-output",
            "start-process"
        }

        if cmd_base not in allowed:
            logger.warning(f"Comando bloqueado: {cmd_base}")
            return

        logger.info(f"PowerShell executado: {command}")

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                logger.info(f"Sucesso: {result.stdout.strip()}")
            else:
                logger.error(f"Erro PS: {result.stderr.strip()}")

        except Exception as e:
            logger.error(f"Erro subprocesso: {e}")

class AIAgentWorker(QThread):
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
        self.stop_signal = True