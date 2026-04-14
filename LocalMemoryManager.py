from loguru import logger
import chromadb
from pathlib import Path
from datetime import datetime
import uuid

BASE_DIR = Path(__file__).resolve().parent

class LocalMemoryManager:
    """Gerencia a memória e contexto do usuário no json"""
    def __init__(self):
        self.db_path = BASE_DIR / "Mika_chrome_db"

        try:
            self.client = chromadb.PersistentClient(path=str(self.db_path))

            self.collection = self.client.get_or_create_collection(name="Mika_conversation")
            logger.info("ChromaDB: Memoria de longo prazo carregada com sucesso")
        except Exception as erro:
            logger.error(f"Erro na inicialização de ChromaDB: {erro}")
        
        self.short_term_memory = []
    
    def add_history(self, user_text, mika_response):
        timestamp = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        interactions_id= str(uuid.uuid4())[:5]

        document = f"Usuario disse:{user_text}\nMika Respondeu: {mika_response}"

        try:
            self.collection.add(
                documents=[document],
                metadatas=[{"timestamp": timestamp}],
                ids=[interactions_id]
            )
        except Exception as erro:
            logger.error(f"Erro ao salvar memoria longa: {erro}")

        self.short_term_memory.append({"user":user_text, "mika": mika_response})
        if len(self.short_term_memory)>3:
            self.short_term_memory.pop(0)
    
    def search_memory(self, query_text, n_results=2):
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            if results and results['documents'] and results['documents'][0]:
                return results['documents'][0]
            return []
        except Exception as erro:
            logger.error(f"Erro ao buscar memoria: {erro}")

