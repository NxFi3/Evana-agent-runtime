#src/Memory/MemoryCache.py

from src.Utils.logger import get_logger
from src.Memory.MemoryEvent import MemoryEvent
import pickle 
import os 
logger = get_logger('[CACHE]')


class MemoryCache:
    def __init__(self) -> None:
        self.cache_path = 'data/MemoryTemporalCache.pkl' # Hard Path
        self.database = self._readpath()
        self.counts = len(self.database)
    def _readpath(self):
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path,'rb') as f:
                    return pickle.load(f)
            else:
                return []
        except Exception as e:
            logger.error(f'Error While Reading Cache : {e} Cannot Load Pervious Cache File')
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
            logger.error(f'Cant Save TemporalCache Error: {e}')
            return False
        
    def flush(self):
        self.database = []
        self.counts = 0

        try:
            if os.path.exists(self.cache_path):
                os.remove(self.cache_path)
            return True
        except Exception as e:
            logger.error(f'Cannot Flush Cache From Disk: {e}')
            return False
    
    def is_empty(self):
        return len(self.database) == 0
    def should_consolidate(self):
        if len(self.database) >=100:
            logger.info(f'Cache OverFlow Require consolidation')
            return True
        else:
            return False        
    def getlen(self):

        return len(self.database)
    
    def add(self,Memory:MemoryEvent):
        if not isinstance(Memory,MemoryEvent):
            logger.warning(f'invalid Format Type {type(Memory)}')
            return False 
        
        self.database.append(Memory)
        self.counts = len(self.database)
        if self.counts % 10 ==0:
            self.SaveTemporalCache()
            logger.info('Saving Cache')
        return True
    
    def getall(self):
        return self.database