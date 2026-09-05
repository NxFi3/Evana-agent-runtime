#src/Memory/ShortTermMemory/stm.py
import os
import pickle
from typing import Any, Dict
from src.Utils.logger import get_logger
from src.Memory.MemoryEvent import MemoryEvent
from src.Memory.ShortTermMemory.MemoryCache import MemoryCache

logger = get_logger('[STM]')


class STM:

    def __init__(self, config: Dict[Any, object], memory_cache: MemoryCache):
        self.config = config
        self.database = self._loaddb()
        self.memorycache = memory_cache
        self.maxstepsSize = config.get('maxsteps',1000)
    def _loaddb(self):
        self.path = self.config.get('stmpath', 'data/stm.pkl')

        try:
            if os.path.exists(self.path):
                with open(self.path, 'rb') as f:
                    return pickle.load(f)
            return []
        except Exception as e:
            logger.error(f'Error While Reading STM : {e}')
            return []

    def save(self):
        try:
            directory = os.path.dirname(self.path)

            if directory:
                os.makedirs(directory, exist_ok=True)

            with open(self.path, 'wb') as f:
                pickle.dump(self.database, f)

            return True

        except Exception as e:
            logger.error(f'Cant Save STM Error: {e}')
            return False

    def add(self, event: MemoryEvent):
        if not isinstance(event, MemoryEvent):
            logger.warning(f'Invalid Event Type: {type(event)}')
            return False

        self.database.append(event)
        if len(self.database) > self.maxstepsSize:
            self.database = self.database[-self.maxstepsSize:]
        self.memorycache.add(event)

        return True

    def getPreviousSteps(self, k: int = 10):
        if k <= 0:
            return []

        return self.database[-k:]

    def getAll(self):
        return self.database

    def size(self):
        return len(self.database)

    def isEmpty(self):
        return len(self.database) == 0

    def flushEverything(self):
        self.memorycache.flush()
        self.database = []

        try:
            if os.path.exists(self.path):
                os.remove(self.path)

            return True

        except Exception as e:
            logger.error(f'Cannot Flush STM: {e}')
            return False
    