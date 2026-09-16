# src/Engine/EmbeddingModel.py

from src.Utils.logger import get_logger
from sentence_transformers import SentenceTransformer
import numpy as np

logger = get_logger("[EMBEDDING]")


class EmbeddingModel:

    def __init__(self, model_name: str = None):

        self.default_model = "intfloat/multilingual-e5-base"
        model_name = model_name or self.default_model

        try:
            logger.info(f"Loading embedding model: {model_name}")

            self.model = SentenceTransformer(model_name)
            self.dimension = int(self.model.get_sentence_embedding_dimension())
        except Exception as e:
            logger.error(f"Error while loading embedding model: {e}")
            logger.warning(f"Trying default model: {self.default_model}")
            self.model = SentenceTransformer(self.default_model)
            self.dimension = (self.model.get_sentence_embedding_dimension())
    
    def encode(self, text: str) -> np.ndarray:

        return self.model.encode(text,normalize_embeddings=True).reshape(1,-1)