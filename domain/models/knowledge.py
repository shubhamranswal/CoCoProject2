"""Engineering document and knowledge models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
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
