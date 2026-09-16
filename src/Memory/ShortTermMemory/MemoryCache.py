#src/Memory/ShortTermMemory/MemoryCache.py

import os
import pickle
from src.Utils.logger import get_logger
from src.Memory.MemoryEvent import MemoryEvent


logger = get_logger('[CACHE]')


class MemoryCache:

    def __init__(self, cache_path: str = 'data/MemoryTemporalCache.pkl'):

        self.cache_path = cache_path
        self.database = self._readpath()
        self.counts = len(self.database)

    def _readpath(self):

        try:

            if not os.path.exists(self.cache_path):
                return []

            with open(self.cache_path, 'rb') as f:
                database = pickle.load(f)

            if not isinstance(database, list):
                logger.warning('Invalid Cache Database Format')
                return []

            return [
                item for item in database
                if isinstance(item, MemoryEvent)
            ]

        except Exception as e:

            logger.error(
                f'Error While Reading Cache: {e}'
            )

            return []

    def SaveTemporalCache(self):

        try:

            directory = os.path.dirname(self.cache_path)

            if directory:
                os.makedirs(directory, exist_ok=True)

            with open(self.cache_path, 'wb') as f:
                pickle.dump(self.database, f)

            return True

        except Exception as e:

            logger.error(
                f'Cant Save TemporalCache Error: {e}'
            )

            return False

    def flush(self):

        try:

            self.database = []
            self.counts = 0

            if os.path.exists(self.cache_path):
                os.remove(self.cache_path)

            return True

        except Exception as e:

            logger.error(
                f'Cannot Flush Cache From Disk: {e}'
            )

            return False

    def is_empty(self):

        return len(self.database) == 0

    def should_consolidate(self):

        return len(self.database) >= 100

    def getlen(self):

        return len(self.database)

    def add(self, memory: MemoryEvent):

        if not isinstance(memory, MemoryEvent):

            logger.warning(
                f'Invalid Format Type: {type(memory)}'
            )

            return False

        self.database.append(memory)
        self.counts = len(self.database)

        if self.counts % 10 == 0:

            if self.SaveTemporalCache():
                logger.info('Saving Cache')

        return True

    def getall(self):

        return self.database