#src/Memory/ShortTermMemory/STM.py

import os
import pickle
from typing import Any, Dict

from src.Utils.logger import get_logger
from src.Memory.MemoryEvent import MemoryEvent
from src.Memory.ShortTermMemory.MemoryCache import MemoryCache


logger = get_logger('[STM]')


class STM:

    def __init__(
        self,
        config: Dict[Any, object],
        memory_cache: MemoryCache
    ):

        self.config = config
        self.memorycache = memory_cache

        self.path = self.config.get(
            'stmpath',
            'data/stm.pkl'
        )

        self.maxstepsSize = max(
            int(self.config.get('maxsteps',1000)),1)

        self.database = self._loaddb()

    def _loaddb(self):

        try:

            if not os.path.exists(self.path):
                return []

            with open(
                self.path,
                'rb'
            ) as f:

                database = pickle.load(f)

            if not isinstance(
                database,
                list
            ):

                logger.warning(
                    'Invalid STM database format'
                )

                return []

            database = [
                event
                for event in database
                if isinstance(
                    event,
                    MemoryEvent
                )
            ]

            if len(database) > self.maxstepsSize:

                database = database[
                    -self.maxstepsSize:
                ]

            return database

        except Exception as e:

            logger.error(
                f'Error While Reading STM : {e}'
            )

            return []

    def save(self):

        try:

            directory = os.path.dirname(
                self.path
            )

            if directory:

                os.makedirs(
                    directory,
                    exist_ok=True
                )

            with open(
                self.path,
                'wb'
            ) as f:

                pickle.dump(
                    self.database,
                    f
                )

            return True

        except Exception as e:

            logger.error(
                f'Cant Save STM Error: {e}'
            )

            return False

    def add(
        self,
        event: MemoryEvent
    ):

        if not isinstance(
            event,
            MemoryEvent
        ):

            logger.warning(
                f'Invalid Event Type: {type(event)}'
            )

            return False

        if not self.memorycache.add(
            event
        ):

            logger.error(
                'Failed to add event to MemoryCache'
            )

            return False

        self.database.append(
            event
        )

        if len(self.database) > self.maxstepsSize:

            self.database = self.database[
                -self.maxstepsSize:
            ]

        return True

    def getPreviousSteps(
        self,
        k: int = 10
    ):

        if k <= 0:
            return []

        return self.database[-k:]

    def getAll(self):

        return self.database

    def size(self):

        return len(
            self.database
        )

    def isEmpty(self):

        return len(
            self.database
        ) == 0

    def flushEverything(self):

        cache_flushed = (
            self.memorycache.flush()
        )

        if not cache_flushed:

            logger.error(
                'Cannot flush MemoryCache'
            )

            return False

        self.database = []

        try:

            if os.path.exists(
                self.path
            ):

                os.remove(
                    self.path
                )

            return True

        except Exception as e:

            logger.error(
                f'Cannot Flush STM: {e}'
            )

            return False