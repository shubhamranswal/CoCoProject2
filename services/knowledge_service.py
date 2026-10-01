"""Knowledge retrieval service with deterministic and Snowflake Cortex Search adapters.

Follows Phase 22:
- KnowledgeRetriever abstract interface
- DeterministicKnowledgeRetriever (lexical / token / tag matching over repository documents)
- CortexSearchKnowledgeRetriever (Snowflake Cortex Search API with deterministic fallback)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from domain.models import Document
from repositories.base import KnowledgeRepository
from tools.read.knowledge_tools import KnowledgeChunkSummary

logger = logging.getLogger(__name__)


class KnowledgeRetriever(ABC):
    """Abstract base class for engineering knowledge retrieval."""

    @abstractmethod
    def search(
        self,
        query: str,
        machine_model: Optional[str] = None,
        failure_mode: Optional[str] = None,
        limit: int = 5,
    ) -> List[KnowledgeChunkSummary]:
        """Search engineering documents, manuals, and SOPs."""
        ...

    @abstractmethod
    def get_manual(self, machine_model: str) -> Optional[Document]:
        """Retrieve complete service manual for an equipment model."""
        ...


class DeterministicKnowledgeRetriever(KnowledgeRetriever):
    """Deterministic in-memory knowledge retriever with lexical relevance ranking."""

    def __init__(self, repo: KnowledgeRepository) -> None:
        self.repo = repo

    def get_manual(self, machine_model: str) -> Optional[Document]:
        return self.repo.get_manual(machine_model)

    def search(
        self,
        query: str,
        machine_model: Optional[str] = None,
        failure_mode: Optional[str] = None,
        limit: int = 5,
    ) -> List[KnowledgeChunkSummary]:
        docs: List[Document] = []
        if machine_model:
            manual = self.repo.get_manual(machine_model)
            if manual:
                docs.append(manual)
        else:
            docs = self.repo.list_documents()

        query_tokens = set(query.lower().split())
        if failure_mode:
            query_tokens.update(failure_mode.lower().replace("_", " ").split())

        matches: List[KnowledgeChunkSummary] = []
        for doc in docs:
            for chunk in doc.chunks:
                chunk_tokens = (
                    set(chunk.content.lower().split())
                    | set(chunk.section_title.lower().split())
                    | {t.lower() for t in chunk.tags}
                )
                overlap = query_tokens.intersection(chunk_tokens)
                if overlap:
                    score = round(len(overlap) / max(len(query_tokens), 1), 2)
                    matches.append(
                        KnowledgeChunkSummary(
                            section_title=f"{doc.title} - {chunk.section_title}",
                            content=chunk.content,
                            relevance_score=score,
                            matched_tags=list(overlap),
                        )
                    )

        matches.sort(key=lambda m: m.relevance_score, reverse=True)
        return matches[:limit]


class CortexSearchKnowledgeRetriever(KnowledgeRetriever):
    """Snowflake Cortex Search knowledge retriever with deterministic fallback."""

    def __init__(
        self,
        repo: KnowledgeRepository,
        snowflake_conn_mgr: Optional[object] = None,
        search_service_name: str = "FACTORY_KNOWLEDGE.MANUAL_SEARCH_SERVICE",
    ) -> None:
        self.repo = repo
        self.conn_mgr = snowflake_conn_mgr
        self.search_service_name = search_service_name
        self.fallback = DeterministicKnowledgeRetriever(repo)

    def get_manual(self, machine_model: str) -> Optional[Document]:
        return self.fallback.get_manual(machine_model)

    def search(
        self,
        query: str,
        machine_model: Optional[str] = None,
        failure_mode: Optional[str] = None,
        limit: int = 5,
    ) -> List[KnowledgeChunkSummary]:
        """Attempt Cortex Search query if live connection available, else fallback."""
        if not self.conn_mgr or not getattr(self.conn_mgr, "is_configured", False):
            logger.info("Snowflake Cortex Search unconfigured; using deterministic knowledge retriever.")
            return self.fallback.search(query, machine_model=machine_model, failure_mode=failure_mode, limit=limit)

        try:
            # Snowflake Cortex Search API invocation
            conn = self.conn_mgr.get_connection()  # type: ignore
            cur = conn.cursor()
            try:
                # Use CORTEX.SEARCH_PREVIEW or custom search service
                cur.execute(
                    "SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW(%s, %s))",
                    (self.search_service_name, query),
                )
                row = cur.fetchone()
                if row and row[0]:
                    import json
                    data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    results = data.get("results", [])
                    summaries: List[KnowledgeChunkSummary] = []
                    for r in results[:limit]:
                        summaries.append(
                            KnowledgeChunkSummary(
                                section_title=r.get("title", "Cortex Search Result"),
                                content=r.get("content", ""),
                                relevance_score=float(r.get("score", 0.9)),
                                matched_tags=["cortex-search"],
                            )
                        )
                    return summaries
            finally:
                cur.close()
                conn.close()
        except Exception as e:
            logger.warning("Cortex Search query failed (%s); falling back to deterministic search.", e)

        return self.fallback.search(query, machine_model=machine_model, failure_mode=failure_mode, limit=limit)
