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


TYPE_SCORES = {
    'user_input': 0.8,
    'agent_action': 0.7,
    'tool_result': 0.6,
    'tool_call': 0.4,
    'system_event': 0.2
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

    def _Candidates(
        self,
        data: List[MemoryEvent]
    ):

        ranked = []

        data = [
            event
            for event in data
            if isinstance(event, MemoryEvent)
            and event.content is not None
            and event.content.strip()
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

            score = (
                0.5 * type_score
                + 0.5 * source_score
            )

            ranked.append(
                (item, score)
            )

        ranked.sort(
            key=lambda x: x[1],
            reverse=True
        )

        results = []

        for event, rank_score in ranked:

            nearest = self.retrieval.get_nearest_memory(
                event.content
            )

            results.append({
                'event': event,
                'rank_score': rank_score,
                'related_memory': (
                    {
                        'id': nearest['id'],
                        'similarity': nearest['similarity']
                    }
                    if nearest is not None
                    else None
                )
            })

        return results

    def _ContextBuild(
        self,
        data: list
    ):

        context = '\n\n'.join(
            f"Content: {item['event'].content}\n"
            f"Event Type: {item['event'].event_type}\n"
            f"Source: {item['event'].source}\n"
            f"Score: {item['rank_score']:.3f}\n"
            f"Similarity: "
            f"{item['related_memory']['similarity']:.3f}"
            if item['related_memory']
            else
            f"Content: {item['event'].content}\n"
            f"Event Type: {item['event'].event_type}\n"
            f"Source: {item['event'].source}\n"
            f"Score: {item['rank_score']:.3f}\n"
            f"Similarity: None"
            for item in data
        )

        return context

    def process(
        self,
        cache: List[MemoryEvent]
    ):

        if not cache:
            return []

        candidates = self._Candidates(
            cache
        )

        if not candidates:
            return []

        context = self._ContextBuild(
            candidates
        )

        prompt = build_decision_prompt(
            context
        )

        response = self.llmprovider.generate(
            prompt
        )

        return self.parser.parse(
            response
        )