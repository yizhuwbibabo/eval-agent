"""Trace importer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentevalops.schemas.trace import Trace


class ImportWarning(BaseModel):
    """A non-fatal problem with one record, including explicit data-loss notes."""

    code: str
    message: str
    field: str | None = None
    trace_id: str | None = None
    record_index: int | None = None
    unparsed_fields: list[str] = Field(default_factory=list)


class FailedRecord(BaseModel):
    record_index: int | None = None
    error: str
    code: str = "IMPORT_ERROR"
    raw_preview: str | None = None


class ImportResult(BaseModel):
    source_type: str
    traces: list[Trace] = Field(default_factory=list)
    warnings: list[ImportWarning] = Field(default_factory=list)
    failed_records: list[FailedRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceImporter(ABC):
    """Base class for trace importers.

    Importers must never silently drop data: fields they cannot parse are
    reported via ``ImportWarning.unparsed_fields``.
    """

    name: str = "base"

    @abstractmethod
    def import_file(self, path: str | Path) -> ImportResult: ...

    @abstractmethod
    def import_string(self, content: str) -> ImportResult: ...
