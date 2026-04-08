from pathlib import Path
from loguru import logger
import pygame
import edge_tts
import warnings

BASE_DIR = Path(__file__).resolve().parent

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