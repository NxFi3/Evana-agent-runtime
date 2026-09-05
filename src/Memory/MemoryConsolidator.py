#src/Memory/MemoryConsolidator.py

from typing import List
from src.Utils.logger import get_logger 
from src.Memory.Retrieval import Retrieval
from src.Engine.llmManagment.LlmProvider import LlmProvider
from src.Memory.DatabaseManager import DBManager
from src.Memory.MemoryEvent import MemoryEvent
from src.Memory.MemoryPrompt import build_decision_prompt 
from src.Memory.MemoryParser import MemoryParser

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
    def __init__(
    self,
    llmprovider: LlmProvider,
    database: DBManager,
    retrieval: Retrieval,
    parser: MemoryParser,
    typescores=TYPE_SCORES,
    source_scores=SOURCE_SCORES
) -> None:
        self.llmprovider = llmprovider
        self.db = database
        self.retrieval = retrieval
        self.type_scores = typescores
        self.source_scores = source_scores
        self.parser = parser
    def _Candidates(self, data: List[MemoryEvent]):
        ranked = []

        data = [
            event for event in data
            if event.content is not None and event.content.strip() != ""
        ]

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

        results = []

        for event, rank_score in ranked:
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
            
    def _ContextBuild(self, data: list):
        context = ''.join(
            f"Event: {item['event']}\n"
            f"Score: {item['rank_score']}\n"
            f"Similarity: {item['related_memory']['similarity'] if item['related_memory'] else None}\n\n"
            for item in data
        )
        return context
        
    def process(self, cache: List[MemoryEvent]):
        """ returns a list of memory objects to be stored in the database """
        candidates = self._Candidates(cache)
        context = self._ContextBuild(candidates)
        Prompt = build_decision_prompt(context)
        response = self.llmprovider.generate(Prompt)
        parsed = self.parser.parse(response)
        return parsed


