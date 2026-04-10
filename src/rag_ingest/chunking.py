"""
Updated Chunking — Story-Level Search
=======================================
"""

import hashlib
import logging

logger = logging.getLogger(__name__)


def generate_story_id(doc_title: str, story_title: str) -> str:
    """Generate a deterministic unique ID for a story across documents."""
    raw = f"{doc_title}::{story_title}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def safe_get(data, key, default="NA"):
    value = data.get(key)
    return value if value is not None else default


def chunk_for_storage(extracted_json: dict) -> dict[str, list[dict]]:
    """
    Takes extracted JSON and produces two separate chunk lists:
    
    1. story_chunks  — for semantic search (finding matching stories)
    2. ac_chunks     — for gap analysis (comparing acceptance criteria)
    
    The link between them is story_id in metadata.
    """
    
    doc_title = extracted_json.get("document_title", "Untitled Document")
    doc_summary = extracted_json.get("document_summary", "")
    doc_type = extracted_json.get("document_type", "")
    doc_metadata = extracted_json.get("metadata", {})
    
    story_chunks = []
    ac_chunks = []
    
    for story in extracted_json.get("stories", []):
        story_metadata = story.get("metadata", {})
        
        # ─── Deterministic story ID ───
        story_id = generate_story_id(doc_title, safe_get(story, "title", ""))
        
        # ─── STORY CHUNK (searchable unit) ───
        story_text = f"{safe_get(story, 'title', '')} — {safe_get(story, 'description', '')}"
        
        story_chunks.append({
            "id": story_id,
            "text": story_text,
            "metadata": {
                "story_id": story_id,
                "role": safe_get(story_metadata, "role"),
                "group": safe_get(story_metadata, "group"),
                "doc_epic": safe_get(doc_metadata, "doc_epic"),
                "ac_count": len(story.get("acceptance_criteria", [])),
                "story_title": safe_get(story, "title"),
                "document_type": safe_get(extracted_json, "document_type"),
                "document_title": safe_get(extracted_json, "document_title"),
                "document_summary": safe_get(extracted_json, "document_summary"),
                "doc_application": safe_get(doc_metadata, "doc_application"),
                "story_description": safe_get(story, "description"),
                "story_id_original": safe_get(story, "id"),
            },
        })
        
        # ─── AC CHUNKS (linked to parent story) ───
        if not story_id:
            logger.warning("Could not determine story_id for AC chunks. Defaulting to 'NA'.")
            story_id = "NA"
            
        for ac in story.get("acceptance_criteria", []):
            ac_chunks.append({
                "id": f"{story_id}_{safe_get(ac, 'id', '')}",
                "text": f"{safe_get(ac, 'title', '')} — {safe_get(ac, 'criteria', '')}",
                "metadata": {
                    "ac_id": safe_get(ac, "id"),
                    "ac_title": safe_get(ac, "title"),
                    "story_id": story_id,
                    "story_id_original": safe_get(story, "id"),
                },
            })
    
    return {
        "story_chunks": story_chunks,
        "ac_chunks": ac_chunks,
    }
