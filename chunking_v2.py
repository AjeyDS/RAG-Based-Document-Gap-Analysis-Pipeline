"""
Updated Chunking & Retrieval — Story-Level Search
==================================================
Changes from the previous version:
  OLD: Raw markdown[:8000] as query → noisy, no structure
  NEW: Each story (title + description) is the searchable unit
       ACs are stored separately, retrieved by story_id filter after match

Two collections in your vector DB:
  1. "stories"  — one row per user story, embedded text = title + description
  2. "criteria" — one row per AC, embedded text = ac_title + criteria
                   linked to parent story via metadata.story_id
"""

import json
import hashlib
from typing import Any


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
    
    doc_title = extracted_json["document_title"]
    doc_summary = extracted_json.get("document_summary", "")
    doc_type = extracted_json.get("document_type", "")
    doc_metadata = extracted_json.get("metadata", {})
    
    story_chunks = []
    ac_chunks = []
    
    for story in extracted_json.get("stories", []):
        story_metadata = story.get("metadata", {})
        
        # ─── Deterministic story ID ───
        story_id = generate_story_id(doc_title, story["title"])
        
        # ─── STORY CHUNK (searchable unit) ───
        # This is what gets embedded and searched against
        # when a new document's story needs to find its KB match
        story_text = f"{story['title']} — {story['description']}"
        
        story_chunks.append({
            "id": story_id,
            "text": story_text,
            "metadata": {
                "document_title": doc_title,
                "document_summary": doc_summary,
                "document_type": doc_type,
                "story_id_original": story["id"],  # e.g. "US-1.1"
                "story_title": story["title"],
                "group": story_metadata.get("group"),
                "role": story_metadata.get("role"),
                "ac_count": len(story.get("acceptance_criteria", [])),
                **{f"doc_{k}": v for k, v in doc_metadata.items()},
            },
        })
        
        # ─── AC CHUNKS (linked to parent story) ───
        # These are NOT searched directly
        # They are retrieved by filtering on story_id after match
        for ac in story.get("acceptance_criteria", []):
            ac_chunks.append({
                "id": f"{story_id}_{ac['id']}",
                "text": f"{ac['title']} — {ac['criteria']}",
                "metadata": {
                    "story_id": story_id,           # <-- the link
                    "document_title": doc_title,
                    "story_id_original": story["id"],
                    "story_title": story["title"],
                    "story_description": story["description"],
                    "ac_id": ac["id"],
                    "ac_title": ac["title"],
                    "group": story_metadata.get("group"),
                },
            })
    
    return {
        "story_chunks": story_chunks,
        "ac_chunks": ac_chunks,
    }


# ─────────────────────────────────────────────────────────
# STORAGE — ChromaDB example
# ─────────────────────────────────────────────────────────

def store_in_chromadb(chunks: dict, client):
    """
    Store story and AC chunks in two separate ChromaDB collections.
    
    Args:
        chunks: Output of chunk_for_storage()
        client: chromadb.Client() instance
    """
    
    # Collection 1: Stories (semantic search target)
    stories_col = client.get_or_create_collection(
        name="stories",
        metadata={"description": "Story-level chunks for semantic matching"}
    )
    
    if chunks["story_chunks"]:
        stories_col.upsert(
            ids=[c["id"] for c in chunks["story_chunks"]],
            documents=[c["text"] for c in chunks["story_chunks"]],
            metadatas=[c["metadata"] for c in chunks["story_chunks"]],
        )
    
    # Collection 2: Acceptance Criteria (retrieved by story_id filter)
    criteria_col = client.get_or_create_collection(
        name="criteria",
        metadata={"description": "AC-level chunks linked to parent stories"}
    )
    
    if chunks["ac_chunks"]:
        criteria_col.upsert(
            ids=[c["id"] for c in chunks["ac_chunks"]],
            documents=[c["text"] for c in chunks["ac_chunks"]],
            metadatas=[c["metadata"] for c in chunks["ac_chunks"]],
        )
    
    print(f"Stored {len(chunks['story_chunks'])} stories, {len(chunks['ac_chunks'])} ACs")


# ─────────────────────────────────────────────────────────
# RETRIEVAL — Story-first, then AC pull
# ─────────────────────────────────────────────────────────

def find_matching_stories(new_extracted_json: dict, client, top_k: int = 3) -> list[dict]:
    """
    For each story in the new document, find the best matching
    story in the knowledge base and pull its ACs.
    
    Args:
        new_extracted_json: Extracted JSON of the newly uploaded document
        client: chromadb.Client() instance
        top_k: Number of candidate matches per story
    
    Returns:
        List of match results, one per new story:
        [
            {
                "new_story": { id, title, description, acceptance_criteria },
                "matched_story": { id, title, description, similarity },
                "matched_acs": [ { id, title, criteria }, ... ]
            },
            ...
        ]
    """
    
    stories_col = client.get_collection("stories")
    criteria_col = client.get_collection("criteria")
    
    results = []
    
    for story in new_extracted_json.get("stories", []):
        
        # ─── Step 1: Semantic search at story level ───
        query_text = f"{story['title']} — {story['description']}"
        
        search_results = stories_col.query(
            query_texts=[query_text],
            n_results=top_k,
        )
        
        if not search_results["ids"][0]:
            results.append({
                "new_story": story,
                "matched_story": None,
                "matched_acs": [],
            })
            continue
        
        # Best match
        best_id = search_results["ids"][0][0]
        best_metadata = search_results["metadatas"][0][0]
        best_distance = search_results["distances"][0][0]
        best_document = search_results["documents"][0][0]
        
        # Convert distance to similarity percentage
        # ChromaDB uses L2 distance by default; cosine needs config
        # For cosine distance: similarity = (1 - distance) * 100
        # For L2 distance: similarity = max(0, (1 - distance/2)) * 100
        similarity = round(max(0, (1 - best_distance)) * 100, 1)
        
        # ─── Step 2: Pull ACs by story_id filter ───
        # This is NOT a semantic search — it's a metadata filter
        ac_results = criteria_col.get(
            where={"story_id": best_id},
        )
        
        matched_acs = []
        if ac_results["ids"]:
            for i, ac_id in enumerate(ac_results["ids"]):
                matched_acs.append({
                    "id": ac_results["metadatas"][i].get("ac_id"),
                    "title": ac_results["metadatas"][i].get("ac_title"),
                    "criteria": ac_results["documents"][i],
                })
        
        results.append({
            "new_story": story,
            "matched_story": {
                "id": best_id,
                "title": best_metadata.get("story_title"),
                "document_title": best_metadata.get("document_title"),
                "similarity": similarity,
                "description": best_document,
            },
            "matched_acs": matched_acs,
        })
    
    return results


# ─────────────────────────────────────────────────────────
# FULL FLOW — Upload → Match → Prepare for Gap Analysis
# ─────────────────────────────────────────────────────────

def prepare_gap_analysis_inputs(new_extracted_json: dict, client) -> list[dict]:
    """
    Complete retrieval flow: for each story in the new document,
    find the matching KB story and prepare inputs for the gap
    analysis LLM prompt.
    
    Returns a list of prompt-ready dicts, one per story pair:
    [
        {
            "new_document_title": "...",
            "existing_document_title": "...",
            "new_story_title": "US-1.1 Vendor Master Sync",
            "similarity": 87.3,
            "new_acceptance_criteria": [...],    # ready for prompt
            "existing_acceptance_criteria": [...] # ready for prompt
        },
        ...
    ]
    """
    
    matches = find_matching_stories(new_extracted_json, client)
    
    prompt_inputs = []
    
    for match in matches:
        if not match["matched_story"]:
            # No KB match found — all ACs are gaps by default
            prompt_inputs.append({
                "new_document_title": new_extracted_json["document_title"],
                "existing_document_title": "No match found",
                "new_story_title": match["new_story"]["title"],
                "similarity": 0,
                "new_acceptance_criteria": match["new_story"].get("acceptance_criteria", []),
                "existing_acceptance_criteria": [],
            })
            continue
        
        prompt_inputs.append({
            "new_document_title": new_extracted_json["document_title"],
            "existing_document_title": match["matched_story"]["document_title"],
            "new_story_title": match["new_story"]["title"],
            "similarity": match["matched_story"]["similarity"],
            "new_acceptance_criteria": match["new_story"].get("acceptance_criteria", []),
            "existing_acceptance_criteria": match["matched_acs"],
        })
    
    return prompt_inputs


# ─────────────────────────────────────────────────────────
# USAGE EXAMPLE
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    
    sample_json = {
        "document_title": "RISE BRD 2 – Vendor Qualification & Surveillance Management",
        "document_summary": "End-to-end digital management of vendor qualification workflows.",
        "document_type": "BRD",
        "metadata": {"epic": "Vendor Qualification", "application": "InLumin"},
        "stories": [
            {
                "id": "US-1.1",
                "title": "Vendor Master Synchronization",
                "description": "Vendor master data should be synchronized automatically from SAP so that InLumin always uses validated and up-to-date vendor records via hourly RFC integration.",
                "acceptance_criteria": [
                    {"id": "AC-1.1", "title": "SAP Sync Execution", "criteria": "Given SAP RFC active, when hourly job runs, then data fetched, duplicates prevented, logs stored."},
                    {"id": "AC-1.2", "title": "Mandatory Field Validation", "criteria": "Given vendor data received, when mandatory fields missing, then record rejected with error."},
                    {"id": "AC-1.3", "title": "Unique Constraint", "criteria": "Given Vendor Code + Company exists, when duplicate received, then update existing, no new record."},
                ],
                "metadata": {"group": "BPR 1 – Vendor Data Management", "role": "Master Data Administrator"},
            },
        ],
    }
    
    chunks = chunk_for_storage(sample_json)
    
    print("=" * 60)
    print(f"STORY CHUNKS: {len(chunks['story_chunks'])}")
    print("=" * 60)
    for s in chunks["story_chunks"]:
        print(f"  ID: {s['id']}")
        print(f"  Text: {s['text'][:80]}...")
        print(f"  AC count: {s['metadata']['ac_count']}")
        print()
    
    print("=" * 60)
    print(f"AC CHUNKS: {len(chunks['ac_chunks'])}")
    print("=" * 60)
    for ac in chunks["ac_chunks"]:
        print(f"  ID: {ac['id']}")
        print(f"  Linked to story: {ac['metadata']['story_id']}")
        print(f"  Text: {ac['text'][:80]}...")
        print()
