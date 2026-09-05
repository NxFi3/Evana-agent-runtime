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
from src.Memory.MemoryConsolidator import MemoryConsolidator
from src.Engine.llmManagment.LlmProvider import LlmProvider
from src.Engine.EmbeddingModel import EmbeddingModel
from src.Engine.RerankerModel import Reranker


logger = get_logger('[MEMORYMANAGER]')


class MemoryManager:

    def __init__(
        self,
        config: dict[Any, object],
        consolidator: MemoryConsolidator,
        stm: STM,
        database: DBManager,
        retrieval: Retrieval,
        llmprovider: LlmProvider,
        embeddingmodel: EmbeddingModel,
        reranker: Reranker
    ):
        self.stm = stm
        self.config = config
        self.llmprovider = llmprovider
        self.embedding = embeddingmodel
        self.reranker = reranker
        self.consolidator = consolidator
        self.db = database
        self.retrieval = retrieval
        self.queue = self._loadqueueCache()
        self.tick = 0

    def _loadqueueCache(self):

        try:

            cache_path = self.config.get(
                'queuecache',
                'queuecache.pkl'
            )

            if not cache_path:
                return []

            if not os.path.exists(cache_path):
                return []

            with open(cache_path, 'rb') as f:
                return pickle.load(f)

        except Exception as e:

            logger.error(
                f"Can't read queue cache: {e}"
            )

            return []

    def step(
        self,
        Event: MemoryEvent
    ):

        if self.stm.add(Event):

            self.tick += 1

            if self.tick >= 100:
                self.saveall()
                self.tick = 0

            return True

        return False

    def ltm_search_tool(
        self,
        query: str
    ) -> list[MemoryItem]:

        try:

            return self.retrieval.Retrieve(query)

        except Exception as e:

            logger.error(
                f'Retrieval Error {e}'
            )

            return []

    def backward(self):

        try:

            if not self.stm.memorycache.should_consolidate():
                return False

            cache = self.stm.memorycache.getall()

            parsed = self.consolidator.process(
                cache
            )

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

                ret = self.retrieval.add(
                    int(memory_id),
                    embedding
                )

                if not ret:

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