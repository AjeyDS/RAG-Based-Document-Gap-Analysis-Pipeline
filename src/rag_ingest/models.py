from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ContentNode:
    node_type: str
    title: str | None = None
    text: str = ""
    level: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    children: list["ContentNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Chunk:
    chunk_id: str
    parent_context: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IngestedDocument:
    source_path: str
    file_type: str
    title: str
    metadata: dict[str, Any]
    text: str
    hierarchy: ContentNode
    chunks: list[Chunk] = field(default_factory=list)
    extracted_json: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["hierarchy"] = self.hierarchy.to_dict()
        data["chunks"] = [chunk.to_dict() for chunk in self.chunks]
        return data
