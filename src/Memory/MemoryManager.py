#src/Memory/MemoryManager.py


import os
import pickle
from typing import Any
from src.Utils.logger import get_logger
from src.Memory.DatabaseManager import DBManager
from src.Memory.MemoryItem import MemoryItem
from src.Memory.MemoryEvent import MemoryEvent
from src.Memory.Retrieval import Retrieval
from src.Memory.ShortTermMemory.STM import STM
from src.Memory.ShortTermMemory.MemoryCache import MemoryCache
from src.Memory.MemoryConsolidator import MemoryConsolidator
from src.Engine.llmManagment.LlmProvider import LlmProvider
from src.Engine.EmbeddingModel import EmbeddingModel
from src.Engine.RerankerModel import Reranker
from src.Memory.MemoryParser import MemoryParser

logger = get_logger('[MEMORYMANAGER]')


class MemoryManager:

    def __init__(
        self,
        config: dict[Any, object],
        llmprovider: LlmProvider,
    ):
        self.config = config
        self.llmprovider = llmprovider

        memorycache_path = self.config.get(
            'memorycachepath',
            'data/MemoryTemporalCache.pkl'
        )
        self.memorycache = MemoryCache(memorycache_path)
        self.stm = STM(
            self.config,
            self.memorycache
        )

        self.embedding = EmbeddingModel()
        self.reranker = Reranker()

        db_path = self.config.get(
            'db_path',
            'data/ltm_database.db'
        )
        self.db = DBManager(db_path)

        index_path = self.config.get(
            'index_path',
            'data/vectors.faiss'
        )

        self.parser = MemoryParser()

        self.retrieval = Retrieval(
            self.embedding,
            self.reranker,
            self.db,
            index_path
        )

        self.consolidator = MemoryConsolidator(
            self.llmprovider,
            self.db,
            self.retrieval,
            self.parser
        )

        self.queue = self._loadqueueCache()
        self.tick = 0

    def _loadqueueCache(self):
        try:
            cache_path = self.config.get(
                'queuecache',
                'queuecache.pkl'
            )

            if not cache_path or not os.path.exists(cache_path):
                return []

            with open(cache_path, 'rb') as f:
                return pickle.load(f)

        except Exception as e:
            logger.error(f"Can't read queue cache: {e}")
            return []

    def step(self, Event: MemoryEvent):
        if self.stm.add(Event):
            self.tick += 1

            if self.tick >= 100:
                self.saveall()
                self.tick = 0

            return True

        return False

    def ltm_search_tool(self, query: str) -> list[MemoryItem]:
        try:
            return self.retrieval.Retrieve(query)
        except Exception as e:
            logger.error(f'Retrieval Error {e}')
            return []

    def backward(self):
        try:
            if not self.stm.memorycache.should_consolidate():
                return False

            cache = self.stm.memorycache.getall()
            parsed = self.consolidator.process(cache)

            success = True

            for item in parsed:
                if item['decision'].lower() != 'create':
                    continue

                value = item['content']

                embedding = self.embedding.encode(
                    f'passage: {value}'
                )

                memory_id = self.db.add_item(
                    value,
                    embedding
                )

                if memory_id is None:
                    success = False
                    continue

                if not self.retrieval.add(
                    int(memory_id),
                    embedding
                ):
                    success = False
                    continue

                self.queue.append(
                    int(memory_id)
                )

            if success:
                self.stm.memorycache.flush()

            return success

        except Exception as e:
            logger.error(
                f'Error From MemoryBackward: {e}'
            )
            return False

    def saveall(self):
        return self.stm.save()

    def get_previous_events(self, k: int = 10):
        return self.stm.getPreviousSteps(k)

