import pygame
import requests
from pathlib import Path
from datetime import datetime
from loguru import logger
import locale
import asyncio
from time import sleep

BASE_DIR = Path(__file__).resolve().parent

class MacroManager:
    #localização da personlizações de macors da mika.
    #funçao principal para chamada de macros.
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    def __init__(self, brain_ref):
        self.brain = brain_ref
    
        self.macros_avaiabilits = {
            "iniciar protocolo": self.macro_welcome,
            "papai chegou": self.macro_welcome
        }

    async def text_process(self, user_text:str)->bool:
        text_lower = user_text.lower()

        for macro, function_macro in self.macros_avaiabilits.items():
            if macro in text_lower:
                logger.info(f"MacroManager: Gatilho detectado -> {macro}")
                await function_macro()
                return True
        return False

    # ===============|
    # FUNÇÕES MACROS |
    # ===============V
# welcome macro function________________________________________________________________________________________________________
    def get_weather(self):
        try:
            url = "https://api.open-meteo.com/v1/forecast?latitude=-23.5489&longitude=-46.6388&current_weather=true"
            response = requests.get(url, timeout=5).json()
            temp = response.get('current_weather', {}).get('temperature', 'desconhecida')
            return f"fazem {temp} graus celsius"
        except Exception as e:
            logger.warning(f"Erro na API de clima: {e}")
            return "não consegui acessar os dados meteorológicos no momento"

    async def macro_welcome(self):
        """Macro: Relatório de sistema com música de fundo"""
        musica_path = BASE_DIR / "BackInBlack.mp3"
        
        # 1. Toca a música
        if musica_path.exists():
            try:
                pygame.mixer.music.load(str(musica_path))
                pygame.mixer.music.set_volume(0.3) 
                pygame.mixer.music.play()
            except Exception as e:
                logger.error(f"Erro ao tocar MP3: {e}")
        else:
            logger.warning(f"Música não encontrada em: {musica_path}")
        
        self.brain.change_anim.emit("happy")
        sleep(1)
        await self.brain.generate_and_queue_tts("Bem vindo senhor.")

        agora = datetime.now()
        data_str = agora.strftime("%d de %B")
        hora_str = agora.strftime("%H:%M")

        clima = await asyncio.to_thread(self.get_weather)

        frases_restantes = [
            f"Hoje é dia {data_str} e agora são {hora_str}.",
            f"A previsão para hoje é {clima}.",
            "Todos os sistemas estão operacionais.",
            "Aguardando suas instruções."
        ]

        for frase in frases_restantes:
            await self.brain.generate_and_queue_tts(frase)
        
        texto_completo = "Bem vindo senhor. " + ' '.join(frases_restantes)
        logger.info(f"Macro Executada: {texto_completo}")
#_________________________________________________________________________________________________________________________
