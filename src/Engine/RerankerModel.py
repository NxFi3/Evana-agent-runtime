# src/Engine/RerankerModel.py

from sentence_transformers import CrossEncoder
from src.Utils.logger import get_logger
logger = get_logger("[RERANKER]")
class Reranker:

    def __init__(self, model_name: str = None):
        self.default_model = "BAAI/bge-reranker-v2-m3"
        model_name = model_name or self.default_model
        try:
            logger.info(f"Loading reranker: {model_name}")
            self.model = CrossEncoder(model_name)
        except Exception as e:

            logger.error(
                f"Error while loading reranker: {e}"
            )

            if model_name != self.default_model:
                logger.warning("Trying default reranker model")
                self.model = CrossEncoder(self.default_model)
            else:
                raise
    def rank(self,query: str,documents: list[str]):
        if not documents:
            return []
        pairs = [
            [query, document]
            for document in documents
        ]

        return self.model.predict(pairs)