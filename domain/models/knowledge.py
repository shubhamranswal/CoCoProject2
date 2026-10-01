"""Engineering document and knowledge models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class KnowledgeChunk(BaseModel):
    chunk_id: str
    document_id: str
    section_title: str
    content: str
    tags: List[str] = Field(default_factory=list)


class Document(BaseModel):
    document_id: str
    title: str
    doc_type: str  # MANUAL, SOP, FAILURE_GUIDE
    machine_model: str  # e.g. DRV-5000
    version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    chunks: List[KnowledgeChunk] = Field(default_factory=list)


class KnowledgeDocument(BaseModel):
    """Canonical knowledge corpus document representing manuals, SOPs, and failure guides."""
    document_id: str
    title: str
    doc_type: str  # MANUAL, SOP, FAILURE_GUIDE, CHECKLIST
    failure_code: Optional[str] = None
    model: Optional[str] = None
    component_type: Optional[str] = None
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FailureModeTaxonomy(BaseModel):
    """Canonical failure mode taxonomy classification."""
    failure_code: str
    failure_name: str
    category: str
    component_type: str
    typical_symptoms: str
    primary_sensors: List[str] = Field(default_factory=list)
    recommended_action: str
