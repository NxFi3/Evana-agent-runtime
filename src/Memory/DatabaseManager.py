# src/Memory/DatabaseManager.py

import sqlite3
import time
from typing import Optional

import numpy as np

from src.Utils.logger import get_logger
from Memory.MemoryItem import MemoryItem


logger = get_logger("DBM")


class DBManager:

    def __init__(self, db_path: str = "") -> None:

        self.database_path = (
            db_path or "Long_Term_Memory.db"
        )

        logger.info(
            f"Using database: {self.database_path}"
        )

        self.create_database()

    def _connect(self):

        conn = sqlite3.connect(
            self.database_path
        )

        conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        return conn

    def create_database(self):

        conn = self._connect()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    graph BLOB,

                    mem_type TEXT NOT NULL,

                    value TEXT NOT NULL,

                    embedding BLOB,

                    created_at REAL NOT NULL,

                    last_access REAL NOT NULL,

                    count INTEGER NOT NULL DEFAULT 1,

                    importance REAL NOT NULL DEFAULT 0.3,

                    deleted INTEGER NOT NULL DEFAULT 0
                )
            """)

            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS items_fts
                USING fts5(
                    value
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_items_mem_type
                ON items(mem_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_items_deleted
                ON items(deleted)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_items_importance
                ON items(importance)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_items_created_at
                ON items(created_at)
            """)

            conn.commit()

            self._sync_fts(cursor)

            conn.commit()

            logger.info(
                "Database initialized successfully"
            )

        except Exception as e:

            conn.rollback()

            logger.error(
                f"Database initialization error: {e}"
            )

            raise

        finally:

            conn.close()

 
    def _sync_fts(self, cursor):

        cursor.execute(
            "SELECT COUNT(*) FROM items"
        )

        item_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM items_fts"
        )

        fts_count = cursor.fetchone()[0]

        if item_count == fts_count:
            return

        logger.info(
            "Synchronizing FTS5 index..."
        )

        cursor.execute(
            "DELETE FROM items_fts"
        )

        cursor.execute("""
            INSERT INTO items_fts(rowid, value)
            SELECT id, value
            FROM items
        """)

    def add_item(
        self,
        value: str,
        embedding: Optional[np.ndarray],
        mem_type: str = "TMode",
        importance: float = 0.3,
        graph: Optional[np.ndarray] = None
    ) -> Optional[int]:

        conn = self._connect()
        cursor = conn.cursor()

        try:

            now = time.time()

            graph_blob = (
                np.asarray(
                    graph,
                    dtype=np.float32
                ).tobytes()
                if graph is not None
                else None
            )

            embedding_blob = (
                np.asarray(
                    embedding,
                    dtype=np.float32
                ).tobytes()
                if embedding is not None
                else None
            )

            cursor.execute("""
                INSERT INTO items (
                    graph,
                    mem_type,
                    value,
                    embedding,
                    created_at,
                    last_access,
                    count,
                    importance,
                    deleted
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                graph_blob,
                mem_type,
                value,
                embedding_blob,
                now,
                now,
                1,
                float(importance)
            ))

            item_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO items_fts(
                    rowid,
                    value
                )
                VALUES (?, ?)
            """, (
                item_id,
                value
            ))

            conn.commit()

            logger.debug(
                f"Added memory item: {item_id}"
            )

            return item_id

        except Exception as e:

            conn.rollback()

            logger.error(
                f"Add item error: {e}"
            )

            return None

        finally:

            conn.close()

    def get_by_id(
        self,
        item_id: int,
        embedding_dtype=np.float32
    ) -> Optional[MemoryItem]:

        conn = self._connect()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT
                    id,
                    graph,
                    mem_type,
                    value,
                    embedding,
                    created_at,
                    last_access,
                    count,
                    importance,
                    deleted
                FROM items
                WHERE id = ?
            """, (item_id,))

            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_memory_item(
                row,
                embedding_dtype
            )

        except Exception as e:

            logger.error(
                f"Get by ID error: {e}"
            )

            return None

        finally:

            conn.close()


    def get_by_ids(
        self,
        item_ids: list[int],
        embedding_dtype=np.float32,
        include_deleted: bool = False
    ) -> list[MemoryItem]:

        if not item_ids:
            return []

        conn = self._connect()
        cursor = conn.cursor()

        try:

            placeholders = ",".join(
                ["?"] * len(item_ids)
            )

            deleted_filter = ""

            if not include_deleted:

                deleted_filter = """
                    AND deleted = 0
                """

            cursor.execute(
                f"""
                SELECT
                    id,
                    graph,
                    mem_type,
                    value,
                    embedding,
                    created_at,
                    last_access,
                    count,
                    importance,
                    deleted
                FROM items
                WHERE id IN ({placeholders})
                {deleted_filter}
                """,
                item_ids
            )

            rows = cursor.fetchall()

            items = [
                self._row_to_memory_item(
                    row,
                    embedding_dtype
                )
                for row in rows
            ]

            item_map = {
                item.id: item
                for item in items
            }

            return [
                item_map[item_id]
                for item_id in item_ids
                if item_id in item_map
            ]

        except Exception as e:

            logger.error(
                f"Get by IDs error: {e}"
            )

            return []

        finally:

            conn.close()


    def search_fts(
        self,
        query: str,
        limit: int = 50,
        include_deleted: bool = False
    ) -> list[MemoryItem]:

        query = query.strip()

        if not query:
            return []

        conn = self._connect()
        cursor = conn.cursor()

        try:

            words = query.split()

            safe_words = []

            for word in words:

                word = "".join(
                    c
                    for c in word
                    if c.isalnum() or c == "_"
                )

                if word:
                    safe_words.append(word)

            if not safe_words:
                return []

            fts_query = " AND ".join(
                f'"{word}"'
                for word in safe_words
            )

            results = self._fts_query(
                cursor,
                fts_query,
                limit,
                include_deleted
            )

            if (
                not results
                and len(safe_words) > 1
            ):

                fts_query = " OR ".join(
                    f'"{word}"'
                    for word in safe_words
                )

                results = self._fts_query(
                    cursor,
                    fts_query,
                    limit,
                    include_deleted
                )

            return [
                self._row_to_memory_item(
                    row,
                    np.float32
                )
                for row in results
            ]

        except Exception as e:

            logger.error(
                f"FTS search error: {e}"
            )

            return []

        finally:

            conn.close()

    def _fts_query(
        self,
        cursor,
        fts_query: str,
        limit: int,
        include_deleted: bool
    ):

        deleted_filter = ""

        if not include_deleted:

            deleted_filter = """
                AND items.deleted = 0
            """

        cursor.execute(
            f"""
            SELECT
                items.id,
                items.graph,
                items.mem_type,
                items.value,
                items.embedding,
                items.created_at,
                items.last_access,
                items.count,
                items.importance,
                items.deleted,
                bm25(items_fts) AS raw_score
            FROM items_fts
            JOIN items
                ON items.id = items_fts.rowid
            WHERE items_fts MATCH ?
            {deleted_filter}
            ORDER BY raw_score
            LIMIT ?
            """,
            (
                fts_query,
                limit
            )
        )

        return cursor.fetchall()


    def update_item(
        self,
        item_id: int,
        new_value: Optional[str] = None,
        new_graph: Optional[np.ndarray] = None,
        new_mem_type: Optional[str] = None,
        new_importance: Optional[float] = None,
        new_embedding: Optional[np.ndarray] = None,
        increment_count: bool = False,
        soft_delete: Optional[bool] = None
    ) -> bool:

        conn = self._connect()
        cursor = conn.cursor()

        try:

            updates = []
            params = []


            if new_value is not None:

                updates.append(
                    "value = ?"
                )

                params.append(
                    new_value
                )

                cursor.execute("""
                    UPDATE items_fts
                    SET value = ?
                    WHERE rowid = ?
                """, (
                    new_value,
                    item_id
                ))


            if new_graph is not None:

                updates.append(
                    "graph = ?"
                )

                params.append(
                    np.asarray(
                        new_graph,
                        dtype=np.float32
                    ).tobytes()
                )


            if new_mem_type is not None:

                updates.append(
                    "mem_type = ?"
                )

                params.append(
                    new_mem_type
                )


            if new_importance is not None:

                updates.append(
                    "importance = ?"
                )

                params.append(
                    float(new_importance)
                )


            if new_embedding is not None:

                updates.append(
                    "embedding = ?"
                )

                params.append(
                    np.asarray(
                        new_embedding,
                        dtype=np.float32
                    ).tobytes()
                )

            if soft_delete is not None:

                updates.append(
                    "deleted = ?"
                )

                params.append(
                    1 if soft_delete else 0
                )

            if increment_count:

                updates.append(
                    "count = count + 1"
                )

            if updates:

                updates.append(
                    "last_access = ?"
                )

                params.append(
                    time.time()
                )

            if not updates:
                return False

            params.append(
                item_id
            )

            query = f"""
                UPDATE items
                SET {", ".join(updates)}
                WHERE id = ?
            """

            cursor.execute(
                query,
                params
            )

            if cursor.rowcount == 0:

                conn.rollback()

                return False

            conn.commit()

            logger.debug(
                f"Updated memory item: {item_id}"
            )

            return True

        except Exception as e:

            conn.rollback()

            logger.error(
                f"Update item error: {e}"
            )

            return False

        finally:

            conn.close()

    def mark_accessed(
        self,
        item_id: int
    ) -> bool:

        conn = self._connect()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                UPDATE items
                SET
                    last_access = ?,
                    count = count + 1
                WHERE id = ?
            """, (
                time.time(),
                item_id
            ))

            conn.commit()

            return cursor.rowcount > 0

        except Exception as e:

            conn.rollback()

            logger.error(
                f"Mark accessed error: {e}"
            )

            return False

        finally:

            conn.close()

    def delete_item(
        self,
        item_id: int,
        hard_delete: bool = False
    ) -> bool:

        if hard_delete:

            conn = self._connect()
            cursor = conn.cursor()

            try:

                cursor.execute("""
                    DELETE FROM items
                    WHERE id = ?
                """, (item_id,))

                deleted = (
                    cursor.rowcount > 0
                )

                cursor.execute("""
                    DELETE FROM items_fts
                    WHERE rowid = ?
                """, (item_id,))

                conn.commit()

                return deleted

            except Exception as e:

                conn.rollback()

                logger.error(
                    f"Hard delete error: {e}"
                )

                return False

            finally:

                conn.close()

        return self.update_item(
            item_id,
            soft_delete=True
        )

    def restore_by_id(
        self,
        item_id: int
    ) -> bool:

        return self.update_item(
            item_id,
            soft_delete=False
        )

    def get_all_embeddings(self):

        conn = self._connect()

        try:

            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    id,
                    embedding
                FROM items
                WHERE deleted = 0
                  AND embedding IS NOT NULL
            """)

            results = []

            for memory_id, embedding_blob in cursor.fetchall():

                embedding = np.frombuffer(
                    embedding_blob,
                    dtype=np.float32
                ).copy()

                results.append(
                    (
                        int(memory_id),
                        embedding
                    )
                )

            return results

        except Exception as e:

            logger.error(
                f"Get all embeddings error: {e}"
            )

            return []

        finally:

            conn.close()

    def database_summary(self) -> dict:

        conn = self._connect()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT COUNT(*)
                FROM items
            """)

            total_items = (
                cursor.fetchone()[0]
            )

            cursor.execute("""
                SELECT
                    mem_type,
                    COUNT(*)
                FROM items
                GROUP BY mem_type
            """)

            type_counts = dict(
                cursor.fetchall()
            )

            cursor.execute("""
                SELECT AVG(importance)
                FROM items
                WHERE deleted = 0
            """)

            avg_importance = (
                cursor.fetchone()[0] or 0
            )

            cursor.execute("""
                SELECT COUNT(*)
                FROM items
                WHERE embedding IS NOT NULL
            """)

            items_with_embedding = (
                cursor.fetchone()[0]
            )

            cursor.execute("""
                SELECT COUNT(*)
                FROM items
                WHERE graph IS NOT NULL
            """)

            items_with_graph = (
                cursor.fetchone()[0]
            )

            cursor.execute("""
                SELECT MAX(last_access)
                FROM items
            """)

            last_update = (
                cursor.fetchone()[0]
            )

            return {
                "total_items": total_items,
                "by_type": type_counts,
                "avg_importance": round(
                    avg_importance,
                    3
                ),
                "items_with_embedding":
                    items_with_embedding,
                "items_with_graph":
                    items_with_graph,
                "last_update":
                    last_update
            }

        except Exception as e:

            logger.error(
                f"Database summary error: {e}"
            )

            return {}

        finally:

            conn.close()

    @staticmethod
    def _row_to_memory_item(
        row,
        embedding_dtype=np.float32
    ) -> MemoryItem:

        graph = (
            np.frombuffer(
                row[1],
                dtype=embedding_dtype
            ).copy()
            if row[1] is not None
            else np.array(
                [],
                dtype=embedding_dtype
            )
        )

        embedding = (
            np.frombuffer(
                row[4],
                dtype=embedding_dtype
            ).copy()
            if row[4] is not None
            else np.array(
                [],
                dtype=embedding_dtype
            )
        )

        raw_score = (
            row[10]
            if len(row) > 10
            else None
        )

        return MemoryItem(
            id=row[0],
            graph=graph,
            mem_type=row[2],
            value=row[3],
            embedding=embedding,
            created_at=row[5],
            last_access=row[6],
            count=row[7],
            importance=row[8],
            deleted=row[9],
            raw_score=raw_score
        )

