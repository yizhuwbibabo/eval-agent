"""Importer registry and dispatch."""

from __future__ import annotations

from pathlib import Path

from agentevalops.ingestion.agenttrek import AgentTrekImporter
from agentevalops.ingestion.base import ImportResult, TraceImporter
from agentevalops.ingestion.inspect_importer import InspectLogImporter
from agentevalops.ingestion.jsonl import JsonlTraceImporter
from agentevalops.ingestion.openai_chat import OpenAIChatImporter

_IMPORTERS: dict[str, TraceImporter] = {
    JsonlTraceImporter.name: JsonlTraceImporter(),
    InspectLogImporter.name: InspectLogImporter(),
    AgentTrekImporter.name: AgentTrekImporter(),
    OpenAIChatImporter.name: OpenAIChatImporter(),
}


def get_importer(name: str) -> TraceImporter:
    if name not in _IMPORTERS:
        raise KeyError(f"unknown importer {name!r}; available: {sorted(_IMPORTERS)}")
    return _IMPORTERS[name]


def detect_importer(path: str | Path) -> str:
    name = str(path).lower()
    if name.endswith(".eval"):
        return "inspect"
    if "agenttrek" in name:
        return "agenttrek"
    return "jsonl"


def import_file(path: str | Path, importer: str | None = None) -> ImportResult:
    importer = importer or detect_importer(path)
    return get_importer(importer).import_file(path)
