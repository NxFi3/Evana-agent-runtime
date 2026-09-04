#src/Memory/MemoryConsolidator.py

from typing import List
from src.Utils.logger import get_logger 
from src.Memory.Retrieval import Retrieval
from src.Engine.llmManagment import LlmProvider
from src.Memory.DatabaseManager import DBManager
from src.Memory.MemoryEvent import MemoryEvent


logger = get_logger('[MCONSOLIDATOR]')

TYPE_SCORES = {'user_input':0.8,
                'agent_action':0.7,
                'tool_result':0.6,
                'tool_call':0.4,
                'system_event':0.2
                }
SOURCE_SCORES = {
    'user': 0.8,
    'llm': 0.6,
    'tool': 0.4,
    'system': 0.2
}

class MemoryConsolidator:
    def __init__(self,llmprovider:LlmProvider,database:DBManager,retrieval:Retrieval,typescores=TYPE_SCORES,source_scores=SOURCE_SCORES) -> None:
        self.LlmProvider = llmprovider 
        self.db = database
        self.retrieval = retrieval
        self.type_scores = typescores
        self.source_scores = source_scores
    def FirstStage(self,data:List[MemoryEvent]):
        data = list(filter(lambda data: data.content is not None and data.content.strip() != "" ,data))
        return data
        
    def Ranker(self, data: List[MemoryEvent]):
        ranked = []

        for item in data:
            type_score = self.type_scores.get(
                item.event_type.lower(),
                0.0
            )

            source_score = self.source_scores.get(
                item.source.lower(),
                0.0
            )

            score = 0.5 * type_score + 0.5 * source_score

            ranked.append((item, score))

        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked
    def secondStage(self, data):
        results = []

        for event, rank_score in data:

            nearest = self.retrieval.get_nearest_memory(
                event.content
            )

            if nearest is None:
                results.append({
                    "event": event,
                    "rank_score": rank_score,
                    "related_memory": None
                })
                continue

            results.append({
                "event": event,
                "rank_score": rank_score,
                "related_memory": {
                    "id": nearest["id"],
                    "similarity": nearest["similarity"]
                }
            })

        return results

    def process(self, cache: List[MemoryEvent]):
        stage_one = self.FirstStage(cache)

        ranked = self.Ranker(stage_one)

        second_stage = self.secondStage(ranked)

        return second_stage
