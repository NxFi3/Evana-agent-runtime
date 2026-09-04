from Memory.MemoryItem import MemoryItem
from src.Engine.EmbeddingModel import EmbeddingModel
from src.Engine.RerankerModel import Reranker
from src.Utils.logger import get_logger
from src.Memory.DatabaseManager import DBManager

from typing import List
import os
import numpy as np
import faiss


logger = get_logger("[RETRIEVAL]")


class Retrieval:

    def __init__(
        self,
        EmbeddingModel: EmbeddingModel,
        Reranker: Reranker,
        DataBase: DBManager,
        index_path: str = "vectors.faiss"
    ) -> None:

        self.EmbeddingModel = EmbeddingModel
        self.Reranker = Reranker
        self.db = DataBase

        self.dimension = (
            self.EmbeddingModel.dimension
        )

        self.index_path = index_path

        self.index = faiss.IndexIDMap2(
            faiss.IndexFlatIP(
                self.dimension
            )
        )

        self._load_or_build_index()
    def _load_or_build_index(self):

        if os.path.exists(
            self.index_path
        ):

            try:

                logger.info(
                    f"Loading FAISS index: "
                    f"{self.index_path}"
                )

                loaded_index = faiss.read_index(
                    self.index_path
                )

                if (
                    loaded_index.d
                    != self.dimension
                ):

                    logger.warning(
                        "FAISS dimension mismatch. "
                        "Rebuilding index."
                    )

                    self._build_index()

                else:

                    self.index = loaded_index

                    logger.info(
                        f"FAISS loaded successfully. "
                        f"Vectors: "
                        f"{self.index.ntotal}"
                    )

            except Exception as e:

                logger.error(
                    f"Failed to load FAISS index: {e}"
                )

                self._build_index()

        else:

            self._build_index()


    def _build_index(self):

        logger.info(
            "Building FAISS index from database..."
        )

        try:

            records = (
                self.db.get_all_embeddings()
            )

            if not records:

                logger.info(
                    "Database contains no embeddings."
                )

                self.index = faiss.IndexIDMap2(
                    faiss.IndexFlatIP(
                        self.dimension
                    )
                )

                return

            ids = []
            embeddings = []

            for memory_id, embedding in records:

                if embedding is None:
                    continue

                embedding = np.asarray(
                    embedding,
                    dtype=np.float32
                ).reshape(1, -1)

                if (
                    embedding.shape[1]
                    != self.dimension
                ):

                    logger.warning(
                        f"Skipping ID {memory_id}: "
                        f"wrong embedding dimension."
                    )

                    continue

                ids.append(
                    int(memory_id)
                )

                embeddings.append(
                    embedding[0]
                )

            if not embeddings:

                self.index = faiss.IndexIDMap2(
                    faiss.IndexFlatIP(
                        self.dimension
                    )
                )

                return

            embeddings = np.asarray(
                embeddings,
                dtype=np.float32
            )

            ids = np.asarray(
                ids,
                dtype=np.int64
            )

            self.index = faiss.IndexIDMap2(
                faiss.IndexFlatIP(
                    self.dimension
                )
            )

            self.index.add_with_ids(
                embeddings,
                ids
            )

            self._save_index()

            logger.info(
                f"FAISS index built. "
                f"Vectors: "
                f"{self.index.ntotal}"
            )

        except Exception as e:

            logger.error(
                f"Failed to build FAISS index: {e}"
            )

            raise

    def _save_index(self):

        try:

            directory = os.path.dirname(
                self.index_path
            )

            if directory:

                os.makedirs(
                    directory,
                    exist_ok=True
                )

            faiss.write_index(
                self.index,
                self.index_path
            )

            logger.debug(
                f"FAISS index saved: "
                f"{self.index_path}"
            )

        except Exception as e:

            logger.error(
                f"Failed to save FAISS index: {e}"
            )

    def add(
        self,
        memory_id: int,
        embedding: np.ndarray
    ):

        if embedding is None:
            return

        embedding = np.asarray(
            embedding,
            dtype=np.float32
        ).reshape(1, -1)

        if (
            embedding.shape[1]
            != self.dimension
        ):

            raise ValueError(
                f"Invalid embedding dimension: "
                f"{embedding.shape[1]} "
                f"(expected {self.dimension})"
            )

        try:

            self.index.remove_ids(
                np.asarray(
                    [memory_id],
                    dtype=np.int64
                )
            )

        except Exception:
            pass

        self.index.add_with_ids(embedding,np.asarray([memory_id],dtype=np.int64))

        self._save_index()

    def remove(
        self,
        memory_id: int
    ):

        self.index.remove_ids(
            np.asarray(
                [memory_id],
                dtype=np.int64
            )
        )

        self._save_index()
    def _dense_search(
        self,
        query_embedding: np.ndarray,
        limit: int = 100
    ):

        if self.index.ntotal == 0:
            return []

        query_embedding = np.asarray(
            query_embedding,
            dtype=np.float32
        ).reshape(1, -1)

        if (
            query_embedding.shape[1]
            != self.dimension
        ):

            raise ValueError(
                f"Invalid query embedding dimension: "
                f"{query_embedding.shape[1]} "
                f"(expected {self.dimension})"
            )

        limit = min(
            limit,
            self.index.ntotal
        )

        distances, ids = (self.index.search(query_embedding,limit))
        results = []

        for rank, (
            memory_id,
            distance
        ) in enumerate(
            zip(
                ids[0],
                distances[0]
            ),
            start=1
        ):

            if memory_id == -1:
                continue

            results.append({
                "id": int(memory_id),
                "rank": rank,
                "distance": float(distance)
            })

        return results
    def _compute_rrf(
        self,
        bm25_results: List[MemoryItem],
        dense_results: list,
        k_rrf: int = 60,
        limit: int = 20
    ):

        """
        Reciprocal Rank Fusion.

        IMPORTANT:
        Uses UNION of BM25 and Dense candidates.

        Example:

        BM25  = [1, 2, 3]
        Dense = [3, 4, 5]

        RRF candidates:
        [1, 2, 3, 4, 5]
        """

        merged = {}
        for rank, item in enumerate(
            bm25_results,
            start=1
        ):

            merged[item.id] = {

                "item": item,

                "rrf_score":
                    1.0 / (
                        k_rrf + rank
                    ),

                "bm25_rank":
                    rank,

                "embedding_rank":
                    None,

                "embedding_distance":
                    None
            }

        dense_only_ids = []
        for result in dense_results:
            memory_id = result["id"]
            if memory_id in merged:
                merged[memory_id][
                    "rrf_score"
                ] += (
                    1.0 / (
                        k_rrf
                        + result["rank"]
                    )
                )

                merged[memory_id][
                    "embedding_rank"
                ] = result["rank"]

                merged[memory_id][
                    "embedding_distance"
                ] = result["distance"]

            else:
                dense_only_ids.append(
                    memory_id
                )

        if dense_only_ids:

            dense_only_items = (
                self.db.get_by_ids(
                    dense_only_ids
                )
            )

            dense_items_map = {
                item.id: item
                for item in dense_only_items
            }

            for result in dense_results:

                memory_id = result["id"]

                if memory_id not in dense_items_map:
                    continue

                if memory_id in merged:
                    continue

                merged[memory_id] = {

                    "item":
                        dense_items_map[
                            memory_id
                        ],

                    "rrf_score":
                        1.0 / (
                            k_rrf
                            + result["rank"]
                        ),

                    "bm25_rank":
                        None,

                    "embedding_rank":
                        result["rank"],

                    "embedding_distance":
                        result["distance"]
                }

        ranked = sorted(
            merged.values(),
            key=lambda x:
                x["rrf_score"],
            reverse=True
        )
        final_items = []

        for data in ranked[:limit]:

            item = data["item"]

            item.rrf_score = (
                data["rrf_score"]
            )

            item.bm25_rank = (
                data["bm25_rank"]
            )

            item.embedding_rank = (
                data["embedding_rank"]
            )

            item.embedding_distance = (
                data["embedding_distance"]
            )

            final_items.append(
                item
            )

        return final_items

    def Retrieve(
        self,
        query: str,
        top_k: int = 10
    ):

        if (
            not query
            or not query.strip()
        ):

            return []
        query_embedding = (
            self.EmbeddingModel.encode(
                f"query: {query}"))

        bm25_results = (
            self.db.search_fts(
                query,
                limit=100))

        dense_results = (
            self._dense_search(
                query_embedding,
                limit=100))


        if (
            not bm25_results
            and not dense_results
        ):

            return []

        rrf_results = (
            self._compute_rrf(
                bm25_results=bm25_results,
                dense_results=dense_results,
                k_rrf=60,
                limit=20))

        if not rrf_results:
            return []

        documents = [
            item.value
            for item in rrf_results]
        reranker_scores = (self.Reranker.rank(query=query,documents=documents))

        for item, score in zip(rrf_results,reranker_scores):

            item.rank = float(score)

        rrf_results.sort(
            key=lambda x:
                x.rank,
            reverse=True
        )


        return rrf_results[:top_k]