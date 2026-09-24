# src/Memory/MemoryManager.py

import os
import pickle
from typing import Any

from src.engine.EmbeddingModel import EmbeddingModel
from src.engine.LlmProviderManager import LlmProvider
from src.engine.RerankerModel import Reranker
from src.memory.DatabaseManager import DBManager
from src.memory.MemoryConsolidator import MemoryConsolidator
from src.memory.MemoryParser import MemoryParser
from src.memory.Retrieval import Retrieval
from src.memory.ShortTermMemory.MemoryCache import MemoryCache
from src.memory.ShortTermMemory.STM import STM
from src.models.MemoryEvent import MemoryEvent
from src.models.MemoryItem import MemoryItem
from src.utils.logger import get_logger

logger = get_logger("[MEMORYMANAGER]")


class MemoryManager:

    def __init__(
        self,
        config: dict[str, Any],
        llmprovider: LlmProvider,
    ) -> None:
        self.config = config
        self.llmprovider = llmprovider

        self.memorycache = self._init_memory_cache()
        self.stm = STM(
            self.config,
            self.memorycache,
        )

        self.embedding = EmbeddingModel()
        self.reranker = Reranker()

        self.db = self._init_database()
        self.retrieval = self._init_retrieval()

        self.parser = MemoryParser()

        self.consolidator = MemoryConsolidator(
            self.llmprovider,
            self.db,
            self.retrieval,
            self.parser,
        )

        self.queue = self._load_queue_cache()
        self.tick = 0

    def _memory_config(self) -> dict[str, Any]:
        nested = self.config.get("memory")

        if isinstance(nested, dict):
            return nested

        return {}

    def _config_value(
        self,
        key: str,
        default: Any,
    ) -> Any:
        memory_config = self._memory_config()

        if key in memory_config:
            return memory_config[key]

        return self.config.get(key, default)

    def _init_memory_cache(self) -> MemoryCache:
        cache_path = self._config_value(
            "memorycachepath",
            "data/MemoryTemporalCache.pkl",
        )

        return MemoryCache(str(cache_path))

    def _init_database(self) -> DBManager:
        db_path = self._config_value(
            "db_path",
            "data/ltm_database.db",
        )

        return DBManager(str(db_path))

    def _init_retrieval(self) -> Retrieval:
        index_path = self._config_value(
            "index_path",
            "data/vectors.faiss",
        )

        return Retrieval(
            self.embedding,
            self.reranker,
            self.db,
            str(index_path),
        )

    def _load_queue_cache(self) -> list[int]:
        cache_path = self._config_value(
            "queuecache",
            "queuecache.pkl",
        )

        if not cache_path:
            return []

        if not os.path.exists(cache_path):
            return []

        try:
            with open(cache_path, "rb") as file:
                queue = pickle.load(file)

            if not isinstance(queue, list):
                logger.warning("Queue cache has invalid format; expected a list.")
                return []

            normalized_queue = []

            for item in queue:
                try:
                    normalized_queue.append(int(item))
                except (TypeError, ValueError):
                    logger.warning(f"Skipping invalid queue item: {item!r}")

            return normalized_queue

        except (OSError, pickle.PickleError) as e:
            logger.error(f"Failed to load queue cache '{cache_path}': {e}")
            return []

        except Exception as e:
            logger.error(f"Unexpected error while loading queue cache: {e}")
            return []

    def step(
        self,
        event: MemoryEvent,
    ) -> bool:
        if not self.stm.add(event):
            return False

        self.tick += 1

        if self.tick >= 100:
            self.saveall()
            self.tick = 0

        return True

    def ltm_search_tool(
        self,
        query: str,
    ) -> list[MemoryItem]:
        if not isinstance(query, str):
            return []

        query = query.strip()

        if not query:
            return []

        try:
            return self.retrieval.Retrieve(query)

        except Exception as e:
            logger.error(f"Long-term memory retrieval failed: {e}")
            return []

    def backward(self) -> bool:
        try:
            if not self.stm.memorycache.should_consolidate():
                return False

            cache = self.stm.memorycache.getall()

            if not cache:
                return False

            parsed = self.consolidator.process(cache)

            if not parsed:
                return False

            success = True

            for item in parsed:
                if not self._process_memory_item(item):
                    success = False

            if success:
                self.stm.memorycache.flush()

            return success

        except Exception as e:
            logger.error(f"Memory consolidation failed: {e}")
            return False

    def _process_memory_item(
        self,
        item: dict[str, Any],
    ) -> bool:
        if not isinstance(item, dict):
            logger.warning(f"Skipping invalid consolidated item: {item!r}")
            return False

        decision = item.get("decision")

        if not isinstance(decision, str):
            logger.warning("Skipping memory item with invalid decision.")
            return False

        if decision.upper() != "CREATE":
            return True

        value = item.get("content")

        if not isinstance(value, str):
            logger.warning("Skipping CREATE item with invalid content.")
            return False

        value = value.strip()

        if not value:
            logger.warning("Skipping CREATE item with empty content.")
            return False

        return self._store_memory(value)

    def _store_memory(
        self,
        value: str,
    ) -> bool:
        try:
            embedding = self.embedding.encode(f"passage: {value}")

            memory_id = self.db.add_item(
                value,
                embedding,
            )

            if memory_id is None:
                logger.error("Failed to persist long-term memory.")
                return False

            memory_id = int(memory_id)

            if not self.retrieval.add(
                memory_id,
                embedding,
            ):
                logger.error(f"Failed to add memory {memory_id} to retrieval index.")
                return False

            self.queue.append(memory_id)

            return True

        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return False

    def saveall(self) -> bool:
        return self.stm.save()

    def get_previous_events(
        self,
        k: int = 10,
    ) -> list[MemoryEvent]:
        if k <= 0:
            return []

        return self.stm.getPreviousSteps(k)

    def get_previous_conversation(
        self,
        k: int = 10,
    ) -> list[MemoryEvent]:
        if k <= 0:
            return []

        events = self.get_previous_events(k * 2)

        conversation = [
            event
            for event in events
            if getattr(event, "source", None)
            in {
                "user",
                "assistant",
            }
        ]

        return conversation[-k:]
