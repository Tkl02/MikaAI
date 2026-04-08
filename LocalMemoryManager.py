from loguru import logger
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class LocalMemoryManager:
    """Gerencia a memória e contexto do usuário no json"""
    def __init__(self):
        self.file_path = BASE_DIR / "MikaMemory.json"
        self.data = self.load_data()

    def load_data(self):
        if self.file_path.exists() and self.file_path.stat().st_size>0:
            try:
                with open(self.file_path, 'r', encoding='utf-8')as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"erro ao ler memoria local {e}")
        else:
            logger.warning("Arquivo de memória não encontrado. Um novo será criado ao salvar dados.")
        return {"preferences":{},"history":[]}

    def save_preference(self, key, value):
        self.data["preferences"][key] = value
        self._sync_to_disk()

    def save_preferenc(self, key, value):
        self.save_preference(key, value)
    
    def add_history(self, user_text, mika_response):
        self.data["history"].append({
            "user": user_text,
            "mika": mika_response,
            "timestamp": "2026-04-07"
        })

        if len(self.data["history"]) > 50:
            self.data["history"].pop(0)
        self._sync_to_disk()
    
    def _sync_to_disk(self):
        try:
            with open(self.file_path,'w', encoding='utf-8')as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar no disco: {e}")
        
    
    def get_context(self):
        return self.data.get("preferences",{})