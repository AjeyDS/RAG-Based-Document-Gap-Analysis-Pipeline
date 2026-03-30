from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

from docling.document_converter import DocumentConverter

from .models import ContentNode, IngestedDocument

if TYPE_CHECKING:
    from .extractor import LLMExtractor

SUPPORTED_SUFFIXES = {
    ".adoc",
    ".asciidoc",
    ".docx",
    ".htm",
    ".html",
    ".md",
    ".pdf",
    ".txt",
}


class Ingestor:
    def __init__(
        self,
        converter: DocumentConverter | None = None,
        extractor: LLMExtractor | None = None,
        progress_cb = None,
    ) -> None:
        self.converter = converter or DocumentConverter()
        self.extractor = extractor
        self.progress_cb = progress_cb or (lambda msg: None)

    def ingest(self, path: str | Path) -> list[IngestedDocument]:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            raise FileNotFoundError(f"Path does not exist: {target}")
        if target.is_dir():
            return [self._ingest_file(p) for p in self._iter_supported_files(target)]
        return [self._ingest_file(target)]

    def _iter_supported_files(self, directory: Path) -> list[Path]:
        return sorted(
            p
            for p in directory.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
        )

    def _ingest_file(self, path: Path) -> IngestedDocument:
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported file type: {path.suffix}")
        if suffix == ".txt":
            return self._ingest_plaintext(path)
        return self._build_document_from_conversion(path, self._convert_with_docling(path))

    def _ingest_plaintext(self, path: Path) -> IngestedDocument:
        title = self._pick_title(path)
        text = path.read_text(encoding="utf-8").strip()
        root = ContentNode(node_type="document", title=title, level=0)
        root.children.append(ContentNode(node_type="body", title=title, text=text, level=1))
        doc = IngestedDocument(
            source_path=str(path),
            file_type="text",
            title=title,
            metadata={"mime_type": self._guess_mime_type(path)},
            text=text,
            hierarchy=root,
        )
        if self.extractor:
            doc.extracted_json = self.extractor.extract(text)
        return doc

    def _convert_with_docling(self, path: Path):
        self.progress_cb("docling")
        import time; time.sleep(1.5)
        return self.converter.convert(str(path))

    def _build_document_from_conversion(self, path: Path, result) -> IngestedDocument:
        hierarchy = self._build_docling_hierarchy(result.document, self._pick_title(path))
        input_format = getattr(getattr(result, "input", None), "format", None)
        page_count = getattr(getattr(result, "input", None), "page_count", None)
        if callable(page_count):
            page_count = page_count()
        if not page_count:
            page_count = getattr(result.document, "num_pages", 0)
            if callable(page_count):
                page_count = page_count()
        title = self._resolve_document_title(hierarchy, path)
        markdown = self._export_markdown(result.document)
        doc = IngestedDocument(
            source_path=str(path),
            file_type=getattr(input_format, "value", path.suffix.lower().lstrip(".")),
            title=title,
            metadata={
                "mime_type": self._guess_mime_type(path),
                "docling_format": getattr(input_format, "value", None),
                "page_count": page_count,
            },
            text=markdown,
            hierarchy=hierarchy,
        )
        if self.extractor:
            self.progress_cb("llm")
            import time; time.sleep(1.5)
            doc.extracted_json = self.extractor.extract(markdown)
        return doc

    def _build_docling_hierarchy(self, document, fallback_title: str) -> ContentNode:
        root = ContentNode(node_type="document", title=fallback_title, level=0)
        stack = [root]
        current = root
        body_node: ContentNode | None = None

        for item, _ in document.iterate_items():
            item_type = type(item).__name__
            if item_type == "TitleItem":
                current = self._push_section(
                    stack=stack,
                    root=root,
                    title=item.text.strip(),
                    level=1,
                    metadata=self._extract_item_metadata(item),
                )
                continue
            if item_type == "SectionHeaderItem":
                current = self._push_section(
                    stack=stack,
                    root=root,
                    title=item.text.strip(),
                    level=int(getattr(item, "level", 1)) + 1,
                    metadata=self._extract_item_metadata(item),
                )
                continue

            item_text = self._extract_item_text(item)
            if not item_text:
                continue

            target = current
            if target is root:
                if body_node is None:
                    body_node = ContentNode(node_type="body", title="Body", level=1)
                    root.children.append(body_node)
                target = body_node

            target.text = self._append_text(target.text, item_text)
            self._merge_metadata(target.metadata, self._extract_item_metadata(item))

        return root

    def _push_section(
        self,
        stack: list[ContentNode],
        root: ContentNode,
        title: str,
        level: int,
        metadata: dict,
    ) -> ContentNode:
        while stack and stack[-1].level >= level:
            stack.pop()
        parent = stack[-1] if stack else root
        node = ContentNode(
            node_type="section",
            title=title,
            level=level,
            metadata=metadata,
        )
        parent.children.append(node)
        stack.append(node)
        return node

    def _extract_item_text(self, item) -> str:
        text = getattr(item, "text", None)
        if text:
            return str(text).strip()
        return ""

    def _extract_item_metadata(self, item) -> dict:
        metadata: dict = {}
        label = getattr(getattr(item, "label", None), "value", None)
        if label:
            metadata["docling_label"] = label
        page_numbers = sorted(
            {
                getattr(prov, "page_no", None)
                for prov in getattr(item, "prov", []) or []
                if getattr(prov, "page_no", None) is not None
            }
        )
        if page_numbers:
            metadata["page_numbers"] = page_numbers
        return metadata

    def _merge_metadata(self, target: dict, updates: dict) -> None:
        for key, value in updates.items():
            if key == "page_numbers" and key in target:
                target[key] = sorted(set(target[key]) | set(value))
            else:
                target.setdefault(key, value)

    def _resolve_document_title(self, hierarchy: ContentNode, path: Path) -> str:
        for child in hierarchy.children:
            if child.node_type == "section" and child.title:
                return child.title
        return self._pick_title(path)

    def _export_markdown(self, document) -> str:
        """Export docling document as full markdown."""
        if hasattr(document, "export_to_markdown"):
            return document.export_to_markdown(image_placeholder="").strip()
        return document.export_to_text().strip()

    def _pick_title(self, path: Path) -> str:
        return path.stem.replace("_", " ").replace("-", " ").strip() or path.name

    def _guess_mime_type(self, path: Path) -> str:
        return mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    def _append_text(self, existing: str, new_text: str) -> str:
        if not existing:
            return new_text
        return f"{existing}\n\n{new_text}"


def ingest_path(path: str | Path) -> list[dict]:
    ingestor = Ingestor()
    return [document.to_dict() for document in ingestor.ingest(path)]


def dumps(documents: list[IngestedDocument | dict]) -> str:
    payload = [
        document.to_dict() if isinstance(document, IngestedDocument) else document
        for document in documents
    ]
    return json.dumps(payload, indent=2, ensure_ascii=True)
