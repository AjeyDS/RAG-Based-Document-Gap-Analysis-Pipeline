"""
Chunking — Structured JSON to Vector DB Rows
=============================================
Takes the structured JSON produced by LLMExtractor and produces chunks
ready for vector DB storage.

Two types of chunks are created:
1. Document-level chunk  — for semantic search (document matching)
2. AC-level chunks       — for gap analysis (comparing acceptance criteria)
"""

from __future__ import annotations

from typing import Any


def chunk_document(extracted_json: dict) -> dict[str, Any]:
    """
    Takes the extracted JSON from LLMExtractor and produces:
    1. A document-level entry for document matching
    2. A list of AC-level chunks for gap analysis

    Args:
        extracted_json: The JSON object returned by LLMExtractor.extract()

    Returns:
        {
            "document_entry": { "text": ..., "metadata": ... },
            "ac_chunks":      [ { "text": ..., "metadata": ... }, ... ]
        }
    """

    stories = extracted_json.get("stories") or []
    
    # ── 1. DOCUMENT-LEVEL ENTRY ──────────────────────────────────────────────
    document_entry = {
        "text": f"{extracted_json.get('document_title')} — {extracted_json.get('document_summary')}",
        "metadata": {
            "document_title": extracted_json.get("document_title"),
            "document_type": extracted_json.get("document_type"),
            "document_summary": extracted_json.get("document_summary"),
            **(extracted_json.get("metadata") or {}),
            "total_stories": len(stories),
            "total_acceptance_criteria": sum(
                len(story.get("acceptance_criteria") or [])
                for story in stories
            ),
        },
    }

    # ── 2. AC-LEVEL CHUNKS ───────────────────────────────────────────────────
    ac_chunks: list[dict[str, Any]] = []

    for story in stories:
        story_metadata = story.get("metadata") or {}

        for ac in (story.get("acceptance_criteria") or []):
            chunk: dict[str, Any] = {
                "text": f"{ac.get('title')} — {ac.get('criteria')}",
                "metadata": {
                    # Document context
                    "document_title": extracted_json.get("document_title"),
                    "document_type": extracted_json.get("document_type"),
                    "document_summary": extracted_json.get("document_summary"),
                    # Story context
                    "story_id": story.get("id"),
                    "story_title": story.get("title"),
                    "story_description": story.get("description"),
                    # AC identity
                    "ac_id": ac.get("id"),
                    "ac_title": ac.get("title"),
                    # Group / module
                    "group": story_metadata.get("group"),
                    "role": story_metadata.get("role"),
                },
            }
            ac_chunks.append(chunk)

    return {
        "document_entry": document_entry,
        "ac_chunks": ac_chunks,
    }
