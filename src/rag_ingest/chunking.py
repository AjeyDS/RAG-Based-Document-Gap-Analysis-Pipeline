"""
Updated Chunking — Story-Level Search
=======================================
"""

import hashlib


def generate_story_id(doc_title: str, story_title: str) -> str:
    """Generate a deterministic unique ID for a story across documents."""
    raw = f"{doc_title}::{story_title}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


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
        story_id = generate_story_id(doc_title, story.get("title", ""))
        
        # ─── STORY CHUNK (searchable unit) ───
        story_text = f"{story.get('title', '')} — {story.get('description', '')}"
        
        story_chunks.append({
            "id": story_id,
            "text": story_text,
            "metadata": {
                "document_title": doc_title,
                "document_summary": doc_summary,
                "document_type": doc_type,
                "story_id_original": story.get("id", ""),
                "story_title": story.get("title", ""),
                "group": story_metadata.get("group"),
                "role": story_metadata.get("role"),
                "ac_count": len(story.get("acceptance_criteria", [])),
                **{f"doc_{k}": v for k, v in doc_metadata.items()},
            },
        })
        
        # ─── AC CHUNKS (linked to parent story) ───
        for ac in story.get("acceptance_criteria", []):
            ac_chunks.append({
                "id": f"{story_id}_{ac.get('id', '')}",
                "text": f"{ac.get('title', '')} — {ac.get('criteria', '')}",
                "metadata": {
                    "story_id": story_id,           # <-- the link
                    "document_title": doc_title,
                    "story_id_original": story.get("id", ""),
                    "story_title": story.get("title", ""),
                    "story_description": story.get("description", ""),
                    "ac_id": ac.get("id", ""),
                    "ac_title": ac.get("title", ""),
                    "group": story_metadata.get("group"),
                },
            })
    
    return {
        "story_chunks": story_chunks,
        "ac_chunks": ac_chunks,
    }
