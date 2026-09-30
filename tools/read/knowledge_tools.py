"""Read tools for technical manuals, SOPs, and engineering knowledge retrieval."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from domain.models import Document
from tools.read.base import BaseReadTool


class GetMachineDocumentationInput(BaseModel):
    machine_model: str = Field(..., description="Target equipment model, e.g. 'DRV-5000'")


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
