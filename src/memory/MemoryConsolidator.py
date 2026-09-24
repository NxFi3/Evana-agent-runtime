# src/Memory/MemoryConsolidator.py

import json
from typing import List

from src.utils.logger import get_logger
from src.memory.Retrieval import Retrieval
from src.engine.LlmProviderManager import LlmProvider
from src.memory.DatabaseManager import DBManager
from src.models.MemoryEvent import MemoryEvent
from src.memory.MemoryPrompt import build_decision_prompt
from src.memory.MemoryParser import MemoryParser

logger = get_logger("[MCONSOLIDATOR]")


TYPE_SCORES = {
    "user_input": 0.8,
    "agent_action": 0.7,
    "tool_result": 0.6,
    "tool_call": 0.4,
    "system_event": 0.2,
}


SOURCE_SCORES = {"user": 0.8, "llm": 0.6, "tool": 0.4, "system": 0.2}


class MemoryConsolidator:

    def __init__(
        self,
        llmprovider: LlmProvider,
        database: DBManager,
        retrieval: Retrieval,
        parser: MemoryParser,
        typescores=TYPE_SCORES,
        source_scores=SOURCE_SCORES,
    ) -> None:

        self.llmprovider = llmprovider
        self.db = database
        self.retrieval = retrieval
        self.type_scores = typescores
        self.source_scores = source_scores
        self.parser = parser

    @staticmethod
    def _event_content(event: MemoryEvent) -> str:
        content = event.content

        if isinstance(content, str):
            return content.strip()

        if content is None:
            return ""

        try:
            return json.dumps(
                content,
                ensure_ascii=False,
                default=str,
            ).strip()
        except Exception:
            return str(content).strip()

    def _Candidates(self, data: List[MemoryEvent]):

        ranked = []

        normalized_events = []

        for event in data:
            if not isinstance(event, MemoryEvent):
                continue

            content = self._event_content(event)

            if not content:
                continue

            normalized_events.append((event, content))

        for event, content in normalized_events:

            type_score = self.type_scores.get(event.event_type.lower(), 0.0)

            source_score = self.source_scores.get(event.source.lower(), 0.0)

            score = 0.5 * type_score + 0.5 * source_score

            ranked.append((event, content, score))

        ranked.sort(key=lambda x: x[2], reverse=True)

        results = []

        for event, content, rank_score in ranked:

            nearest = self.retrieval.get_nearest_memory(content)

            results.append(
                {
                    "event": event,
                    "content": content,
                    "rank_score": rank_score,
                    "related_memory": (
                        {"id": nearest["id"], "similarity": nearest["similarity"]}
                        if nearest is not None
                        else None
                    ),
                }
            )

        return results

    def _ContextBuild(self, data: list):

        context = "

".join(
            (
                f"Content: {item['content']}
"
                f"Event Type: {item['event'].event_type}
"
                f"Source: {item['event'].source}
"
                f"Score: {item['rank_score']:.3f}
"
                f"Similarity: "
                f"{item['related_memory']['similarity']:.3f}"
                if item["related_memory"]
                else f"Content: {item['content']}
"
                f"Event Type: {item['event'].event_type}
"
                f"Source: {item['event'].source}
"
                f"Score: {item['rank_score']:.3f}
"
                f"Similarity: None"
            )
            for item in data
        )

        return context

    def process(self, cache: List[MemoryEvent]):

        if not cache:
            return []

        candidates = self._Candidates(cache)

        if not candidates:
            return []

        context = self._ContextBuild(candidates)

        prompt = build_decision_prompt(context)

        response = self.llmprovider.generate(
            [{"role": "system", "content": prompt}]
        )

        return self.parser.parse(response.response)
