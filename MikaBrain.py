from PyQt6.QtCore import QThread, pyqtSignal
from LocalMemoryManager import LocalMemoryManager
from groq import Groq
from dotenv import load_dotenv
import uuid
import os
from loguru import logger
import shlex
import asyncio
import numpy as np 
import sounddevice as sd
import scipy.io.wavfile as wav
import threading
import keyboard 
import re
from pathlib import Path
import subprocess
import time
from AppOpener import open as open_app
import queue
from kokoro import KPipeline

import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class MikaBrain(QThread):
    #animação
    change_anim = pyqtSignal(str)
    finished_speaking = pyqtSignal()
    change_talking_state = pyqtSignal(bool)

    def __init__(self, windows_ref):
        super().__init__()
        self._run_flag = True 
        self.window = windows_ref 
        self.memory = LocalMemoryManager()
        self.client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
        self.recording_data = []
        self.is_recording = False
        self.is_speaking = False
        self.fs = 16000
        self.system_prompt = self.load_context_file() 
        self.comando_pendente = None

        self.temp_dir = Path(__file__).resolve().parent / "temp_audio"
        self.ensure_temp_dir()
        self.cleanup_temp_files()
        
        logger.info("Carregando modelo Kokoro")
        self.tts_pipeline = KPipeline(lang_code='p')
        self.audio_queue = queue.Queue()
        
        self.playback_thread = threading.Thread(target=self.audio_player_worker, daemon=True)
        self.playback_thread.start()
        
        logger.info("MikaBrain inicializado com sucesso")
        
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
        self.audio_queue.put(None)
    
    def audio_player_worker(self):
        while True:
            audio_data = self.audio_queue.get()
            if audio_data is None:
                logger.info("Thread de áudio encerrada com segurança.")
                break
            audio_array, sr = audio_data

            self.change_talking_state.emit(True)
            sd.play(audio_array, sr)
            sd.wait()
            self.change_talking_state.emit(False)
            self.audio_queue.task_done()

    def listen_windows(self):
        try:
            keyboard.on_press_key('F9', self.handle_key_press)
            keyboard.on_release_key('F9', self.handle_key_release)
            while self._run_flag:
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"Erro no teclado: {e}")
        finally:
            keyboard.unhook_all()

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
    
    def stop_mika_voice(self):
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()
        
        sd.stop()
        self.is_speaking=False

        self.change_anim.emit("neutral")
        self.change_talking_state.emit(False)

        logger.info("Mika: Fala interrompida pelo usuario")
    
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
                msg_contexto = f"[LEMBRANÇAS RELEVANTES DO PASSADO]:\n{contexto_passado}\nUser essa lembranças se forem uteis para o contexto atual"
                messages_list.append({"role":"system","content":msg_contexto})
                logger.info("Memoria antiga resgatada e injetada no prompt")

            for interacao in self.memory.short_term_memory:
                if isinstance(interacao, dict):
                    messages_list.append({"role": "user", "content": interacao["user"]})
                    messages_list.append({"role": "assistant", "content": interacao["mika"]})
            
            messages_list.append({"role": "user", "content": text_input})
            
            chat_compilation = self.client.chat.completions.create(
                messages=messages_list,
                model=MODELO_ATUAL,
                stream=True
            )

            self.is_speaking=True
            self.change_anim.emit("happy")

            texto_completo = ""
            sentenca_buffer = ""

            for chunk in chat_compilation:
                if chunk.choices[0].delta.content:
                    pedaco = chunk.choices[0].delta.content
                    texto_completo += pedaco
                    sentenca_buffer += pedaco

                    if "[[" in sentenca_buffer:
                        if "]]" in sentenca_buffer:
                            sentenca_buffer = re.sub(r'\[\[.*?\]\]', '', sentenca_buffer, flags=re.DOTALL)
                        continue

                    if any(p in sentenca_buffer for p in ['.','!','?','\n']):
                        frase_limmpa = sentenca_buffer.strip()
                        if len(frase_limmpa) >2:
                            generator = self.tts_pipeline(frase_limmpa, voice='pf_dora',speed=1.0)
                            for _, _, audio in generator:
                                self.audio_queue.put((audio, 24000))
                        sentenca_buffer=""
            
            if len(sentenca_buffer.strip()) > 2 and not "[[" in sentenca_buffer:
                generator=self.tts_pipeline(sentenca_buffer.strip(), voice='pf_dora',speed=1.0)
                for _,_,audio in generator:
                    self.audio_queue.put((audio,24000))
            
            logger.info(f"Mika: {texto_completo}")
            self.memory.add_history(text_input, texto_completo)
            self.audio_queue.join()

            self.is_speaking=False
            self.change_anim.emit("neutral")

            command_match = re.search(r'\[\[EXEC:\s*(.+?)\]\]', texto_completo, re.DOTALL)
            open_match = re.search(r'\[\[OPEN:\s*(.+?)\]\]', texto_completo, re.DOTALL)

            if command_match:
                command_raw = command_match.group(1).strip()
                cmd_base = command_raw.split()[0].lower() if command_raw else ""

                if cmd_base in ["remove-item", "rm", "del", "rmdir"]:
                    self.comando_pendente = command_raw
                else:
                    self.exec_command_powershell(command_raw)
            
            if open_match:
                app_to_open = open_match.group(1).strip()
                self.abrir_aplicativo(app_to_open)

        except Exception as e:
            logger.error(f"Erro no pensamento: {e}")
        finally:
            self.is_speaking = False
            self.change_anim.emit("neutral")

    def exec_command_powershell(self, command):
        if not command:
            return

        try:
            parts = shlex.split(command, posix=False)
        except Exception:
            parts = command.split()

        cmd_base = parts[0].lower()

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