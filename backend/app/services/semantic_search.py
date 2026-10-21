"""Local, per-agent semantic retrieval over graph chunks."""

from functools import lru_cache
import re
from app.core.runtime import model_cache_root


EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_INDEX_VERSION = f"{EMBEDDING_MODEL}:wordninja-v1"
EMBEDDING_DIMENSIONS = 384
MIN_SIMILARITY = 0.30
MAX_RESULTS = 6
RERANK_CANDIDATES = 50
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Semantic search is unavailable; install backend requirements") from exc
    try:
        return SentenceTransformer(EMBEDDING_MODEL, device="cpu", local_files_only=True,
                                   cache_folder=str(model_cache_root()))
    except Exception as exc:
        raise RuntimeError(f"Unable to load the cached semantic search model; download it before Self Train: {exc}") from exc


@lru_cache(maxsize=1)
def _reranker():
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder(RERANK_MODEL, device="cpu", local_files_only=True,
                            cache_folder=str(model_cache_root()))
    except Exception as exc:
        raise RuntimeError(f"Unable to load the cached semantic reranker; download it before project chat: {exc}") from exc


def embed_documents(texts: list[str]) -> list[bytes]:
    if not texts:
        return []
    vectors = _model().encode_document([_prepare_text(text) for text in texts],
                                       batch_size=32, normalize_embeddings=True,
                                       convert_to_numpy=True, show_progress_bar=False)
    return [vector.astype("float32").tobytes() for vector in vectors]


def _prepare_text(text: str) -> str:
    """Restore spaces in merged PDF words before embedding, retaining raw source text."""
    try:
        import wordninja
    except ImportError as exc:
        raise RuntimeError("PDF text normalization is unavailable; install backend requirements") from exc
    return re.sub(r"[A-Za-z]{8,}", lambda match: " ".join(wordninja.split(match.group())), text)


def search_agent_chunks(connection, agent_id: int, question: str,
                        project_id: int | None = None) -> list[dict]:
    import numpy as np

    rows = connection.execute(
        """SELECT s.title, s.source_kind, s.project_name, c.locator, c.content,
                  c.embedding, c.embedding_model
        FROM agent_graph_chunks c JOIN agent_graph_sources s
          ON s.agent_id = c.agent_id AND s.source_key = c.source_key
        WHERE c.agent_id = ? AND (? IS NULL OR s.project_id IS NULL OR s.project_id = ?) AND (
          s.source_kind != 'file' OR EXISTS (
            SELECT 1 FROM agent_sources a
            WHERE a.agent_id = s.agent_id AND a.approval_status = 'approved'
              AND s.source_key = 'file:' || a.id
          )
        ) AND (
          s.source_kind != 'task' OR EXISTS (
            SELECT 1 FROM tasks t WHERE t.id = CAST(s.source_id AS INTEGER)
              AND t.project_id = s.project_id AND t.assigned_agent_id = s.agent_id
          )
        ) AND (
          s.source_kind != 'lesson' OR EXISTS (
            SELECT 1 FROM agent_lessons l WHERE l.id = CAST(s.source_id AS INTEGER)
              AND l.agent_id = s.agent_id AND l.approval_status = 'approved'
          )
        ) AND (
          s.source_kind != 'chat' OR EXISTS (
            SELECT 1 FROM messages m
            JOIN conversation_threads ct ON ct.id = m.thread_id
            LEFT JOIN tasks t ON t.id = CAST(json_extract(m.metadata_json, '$.task_id') AS INTEGER)
              AND t.project_id = ct.project_id
            WHERE m.id = CAST(s.source_id AS INTEGER)
              AND ct.project_id = s.project_id
              AND (m.sender_agent_id = s.agent_id OR t.assigned_agent_id = s.agent_id)
          )
        )
        ORDER BY c.source_key, c.chunk_index""", (agent_id, project_id, project_id),
    ).fetchall()
    if not rows:
        return []
    if any(row["embedding"] is None or row["embedding_model"] != EMBEDDING_INDEX_VERSION
           or len(row["embedding"]) != EMBEDDING_DIMENSIONS * 4 for row in rows):
        raise ValueError("Start Self Train to prepare semantic search for this coworker")
    vectors = np.frombuffer(b"".join(row["embedding"] for row in rows),
                            dtype=np.float32).reshape(len(rows), EMBEDDING_DIMENSIONS)
    query = _model().encode_query(_prepare_text(question), normalize_embeddings=True,
                                  convert_to_numpy=True).astype(np.float32)
    scores = vectors @ query
    top = float(scores.max())
    if top < MIN_SIMILARITY:
        return []
    candidates = [int(index) for index in np.argsort(scores)[::-1][:RERANK_CANDIDATES]
                  if scores[index] >= MIN_SIMILARITY]
    passage_scores = _reranker().predict(
        [(question, _prepare_text(rows[index]["content"])) for index in candidates],
        batch_size=16, show_progress_bar=False,
    )
    ranked = sorted(zip(passage_scores, candidates), reverse=True)
    best = float(ranked[0][0])
    return [dict(rows[index]) for score, index in ranked[:MAX_RESULTS]
            if float(score) >= best - 2.0]


def search_related_project_experience(connection, agent_id: int, project_id: int,
                                      human_id: int | None, question: str) -> list[dict]:
    """Retrieve trained task experience only from other projects visible to this human."""
    if human_id is None:
        return []
    import numpy as np

    rows = connection.execute(
        """SELECT s.title, s.project_id, s.project_name, c.locator, c.content,
                  c.embedding, c.embedding_model
           FROM agent_graph_chunks c JOIN agent_graph_sources s
             ON s.agent_id = c.agent_id AND s.source_key = c.source_key
           JOIN projects p ON p.id = s.project_id AND p.status != 'removed' AND p.removed_at IS NULL
           JOIN project_agents pa ON pa.project_id = s.project_id AND pa.agent_id = s.agent_id
             AND pa.status = 'active'
           JOIN project_members pm ON pm.project_id = s.project_id AND pm.human_id = ?
             AND pm.status != 'removed'
           JOIN tasks t ON t.id = CAST(s.source_id AS INTEGER) AND t.project_id = s.project_id
             AND t.assigned_agent_id = s.agent_id
           WHERE c.agent_id = ? AND s.project_id != ? AND s.source_kind = 'task'
           ORDER BY s.project_id, c.source_key, c.chunk_index""",
        (human_id, agent_id, project_id),
    ).fetchall()
    rows = [row for row in rows if row["embedding"] is not None
            and row["embedding_model"] == EMBEDDING_INDEX_VERSION
            and len(row["embedding"]) == EMBEDDING_DIMENSIONS * 4]
    if not rows:
        return []
    vectors = np.frombuffer(b"".join(row["embedding"] for row in rows),
                            dtype=np.float32).reshape(len(rows), EMBEDDING_DIMENSIONS)
    query = _model().encode_query(_prepare_text(question), normalize_embeddings=True,
                                  convert_to_numpy=True).astype(np.float32)
    scores = vectors @ query
    candidates = [int(index) for index in np.argsort(scores)[::-1][:20]
                  if scores[index] >= 0.45]
    if not candidates:
        return []
    passage_scores = _reranker().predict(
        [(question, _prepare_text(rows[index]["content"])) for index in candidates],
        batch_size=16, show_progress_bar=False,
    )
    ranked = sorted(zip(passage_scores, candidates), reverse=True)
    return [dict(rows[index]) for score, index in ranked[:2]
            if float(score) >= float(ranked[0][0]) - 2.0]
