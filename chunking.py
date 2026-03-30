"""
Chunking Step — JSON to Vector DB Rows
=======================================
The implementation lives in the rag_ingest package (src/rag_ingest/chunking.py).
This file re-exports chunk_document for standalone / notebook use.
"""

from rag_ingest.chunking import chunk_document  # noqa: F401

import json


# ─────────────────────────────────────────────────────────
# USAGE EXAMPLE
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":

    sample_json = {
        "document_title": "RISE BRD 2 – Vendor Qualification & Surveillance Management",
        "document_summary": "Defines end-to-end digital management of Vendor Qualification, Requalification, and VSF workflows with automated scheduling, alerts, role-based processing, document control, SLA monitoring, and full audit traceability within InLumin.",
        "document_type": "BRD",
        "metadata": {
            "epic": "Vendor Qualification & Surveillance Management",
            "application": "InLumin",
            "brd_id": "RISE BRD 2",
        },
        "stories": [
            {
                "id": "US-1.1",
                "title": "Vendor Master Synchronization",
                "description": "Vendor master data should be synchronized automatically from SAP (ECC/S4HANA) so that InLumin always uses validated and up-to-date vendor records.",
                "acceptance_criteria": [
                    {
                        "id": "AC-1.1",
                        "title": "SAP Sync Execution",
                        "criteria": "Given the SAP RFC interface is active, when the hourly job runs, then vendor data shall be fetched and updated in InLumin.",
                    },
                    {
                        "id": "AC-1.2",
                        "title": "Mandatory Field Validation",
                        "criteria": "Given vendor data is received, when mandatory fields are missing, then the record shall be rejected and logged.",
                    },
                ],
                "metadata": {
                    "group": "BPR 1 – Vendor Data Management",
                    "role": "Master Data Administrator",
                },
            },
        ],
    }

    result = chunk_document(sample_json)

    print("=" * 60)
    print("DOCUMENT-LEVEL ENTRY (for semantic search)")
    print("=" * 60)
    print(json.dumps(result["document_entry"], indent=2))

    print()
    print("=" * 60)
    print(f"AC-LEVEL CHUNKS ({len(result['ac_chunks'])} total)")
    print("=" * 60)
    for i, chunk in enumerate(result["ac_chunks"], 1):
        print(f"\n--- Chunk {i} ---")
        print(f"Text:     {chunk['text'][:100]}...")
        print(f"Story:    {chunk['metadata']['story_id']} — {chunk['metadata']['story_title']}")
        print(f"AC:       {chunk['metadata']['ac_id']}")
        print(f"Group:    {chunk['metadata']['group']}")
