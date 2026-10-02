"""Read tools for technical manuals, SOPs, and engineering knowledge retrieval."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from domain.models import Document, KnowledgeDocument
from tools.read.base import BaseReadTool


class GetMachineDocumentationInput(BaseModel):
    machine_model: str = Field(..., description="Target equipment model, e.g. 'DRV-5000' or 'GR-600'")


class DocumentOutput(BaseModel):
    machine_model: str
    document: Optional[Document] = None


class GetMachineDocumentationTool(BaseReadTool):
    name = "get_machine_documentation"
    description = "Retrieve the complete official technical service manual and maintenance specifications for an equipment model."
    scope = "knowledge:read"
    input_schema = GetMachineDocumentationInput
    output_schema = DocumentOutput

    def _run(self, params: GetMachineDocumentationInput) -> DocumentOutput:
        doc = self.repo.get_manual(params.machine_model)
        return DocumentOutput(machine_model=params.machine_model, document=doc)


class KnowledgeSearchResultItem(BaseModel):
    document_id: str
    title: str
    document_type: str = "guidance"
    section: Optional[str] = None
    content_excerpt: str
    relevance: float = 1.0
    source_reference: str = ""


class SearchKnowledgeInput(BaseModel):
    query: str = Field(..., description="Technical keywords or failure symptoms to search, e.g. 'bearing vibration degradation'")
    machine_id: Optional[str] = Field(default=None, description="Optional machine ID, e.g. 'M21'")
    component_id: Optional[str] = Field(default=None, description="Optional component ID, e.g. 'C-M21-BRG'")
    failure_code: Optional[str] = Field(default=None, description="Optional failure code, e.g. 'BD-BRG'")
    top_k: int = Field(default=5, ge=1, le=20, description="Max results to retrieve")


class SearchKnowledgeOutput(BaseModel):
    query: str
    results_count: int
    results: List[KnowledgeSearchResultItem] = Field(default_factory=list)


class SearchKnowledgeTool(BaseReadTool):
    name = "search_knowledge"
    description = "Search engineering manuals, ISO vibration severity tables, and maintenance procedures for diagnostic guidance."
    scope = "knowledge:read"
    input_schema = SearchKnowledgeInput
    output_schema = SearchKnowledgeOutput

    def _run(self, params: SearchKnowledgeInput) -> SearchKnowledgeOutput:
        # Check KnowledgeSearchRepository
        search_fn = getattr(self.repo, "search_corpus", None)
        docs: List[KnowledgeDocument] = []
        if callable(search_fn):
            docs = search_fn(query=params.query, limit=params.top_k, failure_code=params.failure_code)

        if not docs:
            # Fallback to list_documents
            list_fn = getattr(self.repo, "list_documents", None)
            if callable(list_fn):
                all_docs = list_fn()
                # Simple keyword filter
                q_words = set(params.query.lower().split())
                for d in all_docs:
                    c_words = set(d.content.lower().split()) if hasattr(d, "content") else set()
                    t_words = set(d.title.lower().split()) if hasattr(d, "title") else set()
                    if q_words.intersection(c_words | t_words):
                        docs.append(d)
                docs = docs[:params.top_k]

        items: List[KnowledgeSearchResultItem] = []
        for d in docs:
            excerpt = d.content[:400] + ("..." if len(d.content) > 400 else "") if hasattr(d, "content") else ""
            doc_id = getattr(d, "document_id", None) or getattr(d, "doc_id", "DOC-001")
            items.append(
                KnowledgeSearchResultItem(
                    document_id=doc_id,
                    title=d.title,
                    document_type=getattr(d, "doc_type", "reference"),
                    content_excerpt=excerpt,
                    relevance=0.92,
                    source_reference=f"Manual:{doc_id}",
                )
            )

        return SearchKnowledgeOutput(
            query=params.query,
            results_count=len(items),
            results=items,
        )


class GetKnowledgeDocumentInput(BaseModel):
    document_id: str = Field(..., description="Document identifier, e.g. 'DOC-001'")


class KnowledgeDocumentOutput(BaseModel):
    document_id: str
    title: str
    document_type: str
    content: str
    machine_type: Optional[str] = None
    component_type: Optional[str] = None


class GetKnowledgeDocumentTool(BaseReadTool):
    name = "get_knowledge_document"
    description = "Retrieve full text content and metadata of a specific engineering knowledge document."
    scope = "knowledge:read"
    input_schema = GetKnowledgeDocumentInput
    output_schema = Optional[KnowledgeDocumentOutput]

    def _run(self, params: GetKnowledgeDocumentInput) -> Optional[KnowledgeDocumentOutput]:
        doc = getattr(self.repo, "get_document", lambda did: None)(params.document_id)
        if not doc:
            return None
        doc_id = getattr(doc, "document_id", None) or getattr(doc, "doc_id", params.document_id)
        doc_type = getattr(doc, "doc_type", "reference")
        m_type = getattr(doc, "machine_type", None) or getattr(doc, "model", None)
        c_type = getattr(doc, "component_type", None)

        return KnowledgeDocumentOutput(
            document_id=doc_id,
            title=doc.title,
            document_type=doc_type,
            content=doc.content,
            machine_type=m_type,
            component_type=c_type,
        )


# Backward compatibility
class GetRelatedKnowledgeInput(BaseModel):
    machine_id: str = Field(..., description="Target machine ID, e.g. 'M204'")
    component_id: Optional[str] = Field(default=None, description="Optional target component ID")
    failure_mode: Optional[str] = Field(default=None, description="Optional failure mode, e.g. 'BEARING_DEGRADATION'")
    query: str = Field(..., description="Keywords or diagnostic topic to search for in engineering guides")


class KnowledgeChunkSummary(BaseModel):
    section_title: str
    content: str
    relevance_score: float = 1.0
    matched_tags: List[str] = Field(default_factory=list)


class KnowledgeSearchOutput(BaseModel):
    query: str
    results_count: int
    results: List[KnowledgeChunkSummary] = Field(default_factory=list)


class GetRelatedKnowledgeTool(BaseReadTool):
    name = "get_related_knowledge"
    description = "Retrieve relevant engineering guidance, diagnostic criteria, and standard operating procedures for a specific problem."
    scope = "knowledge:read"
    input_schema = GetRelatedKnowledgeInput
    output_schema = KnowledgeSearchOutput

    def _run(self, params: GetRelatedKnowledgeInput) -> KnowledgeSearchOutput:
        mach = self.repo.get_machine(params.machine_id)
        model = mach.model if mach else "DRV-5000"
        doc = self.repo.get_manual(model)

        if not doc:
            return KnowledgeSearchOutput(query=params.query, results_count=0, results=[])

        query_tokens = set(params.query.lower().split())
        if params.failure_mode:
            query_tokens.update(params.failure_mode.lower().replace("_", " ").split())
        if params.component_id:
            query_tokens.update(params.component_id.lower().replace("-", " ").split())

        matches: List[KnowledgeChunkSummary] = []
        for chunk in doc.chunks:
            chunk_tokens = set(chunk.content.lower().split()) | set(chunk.section_title.lower().split()) | {t.lower() for t in chunk.tags}
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
        return KnowledgeSearchOutput(
            query=params.query,
            results_count=len(matches),
            results=matches,
        )
