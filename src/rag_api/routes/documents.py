"""Documents module for Document Gap Analysis pipeline."""
from __future__ import annotations

import json
import re
import uuid
import tempfile
from pathlib import Path
from statistics import mean
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile, Depends, Request
from pydantic import BaseModel

from src.rag_api.dependencies import get_vector_store, get_settings, get_pipeline, get_llm
from src.rag_ingest.store import VectorStore
from src.rag_ingest.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

_ROOT = Path(__file__).resolve().parents[3]
_CHUNK_PATTERN = re.compile(r"(\*\*US-\d+\.\d+.*?\*\*|\*\*AC-\d+\.\d+.*?\*\*)")

class CompareRequest(BaseModel):
    uploadedText: str
    matches: list[dict]
    extractedJson: dict | None = None

def find_matching_stories(new_extracted_json: dict, vs: VectorStore, top_k: int = 3) -> list[dict]:
    results = []
    stories = new_extracted_json.get("stories", [])
    if not stories:
        return []
        
    query_texts = [f"{story.get('title', '')} — {story.get('description', '')}" for story in stories]
    all_story_matches = vs.query_stories_batch(query_texts, top_k=top_k)
    
    for i, story in enumerate(stories):
        matches = all_story_matches[i]
        
        if not matches:
            results.append({"new_story": story, "matched_story": None, "matched_acs": []})
            continue
            
        best = matches[0]
        similarity = round(max(0, (1.0 - best["distance"])) * 100, 1)
        
        full_story_id = best["id"]
        actual_story_id = full_story_id.split("::")[-1] if "::" in full_story_id else full_story_id
        ac_matches = vs.get_criteria_for_story(actual_story_id)
        
        matched_acs = []
        for am in ac_matches:
            matched_acs.append({
                "id": am["metadata"].get("ac_id"),
                "title": am["metadata"].get("ac_title"),
                "criteria": am["content"],
            })
                
        source_path = best["metadata"].get("source", best.get("source", ""))
        extracted_filename = Path(source_path).name.split("_", 1)[-1] if "_" in Path(source_path).name else Path(source_path).name
        
        results.append({
            "new_story": story,
            "matched_story": {
                "id": best["id"],
                "title": best["metadata"].get("story_title"),
                "document_title": extracted_filename,
                "similarity": similarity,
                "description": best["document"],
            },
            "matched_acs": matched_acs,
        })
    return results

def prepare_gap_analysis_inputs(new_extracted_json: dict, vs: VectorStore) -> list[dict]:
    matches = find_matching_stories(new_extracted_json, vs)
    prompt_inputs = []
    for match in matches:
        if not match["matched_story"]:
            prompt_inputs.append({
                "new_document_title": new_extracted_json.get("document_title", "Uploaded Document"),
                "existing_document_title": "No match found",
                "new_story_title": match["new_story"].get("title", ""),
                "similarity": 0,
                "new_acceptance_criteria": match["new_story"].get("acceptance_criteria", []),
                "existing_acceptance_criteria": [],
            })
            continue
            
        prompt_inputs.append({
            "new_document_title": new_extracted_json.get("document_title", "Uploaded Document"),
            "existing_document_title": match["matched_story"]["document_title"],
            "new_story_title": match["new_story"].get("title", ""),
            "similarity": match["matched_story"]["similarity"],
            "new_acceptance_criteria": match["new_story"].get("acceptance_criteria", []),
            "existing_acceptance_criteria": match["matched_acs"],
        })
        
    return prompt_inputs

@router.post("/upload")
async def upload_and_search(
    request: Request,
    file: UploadFile = File(...),
    vs: VectorStore = Depends(get_vector_store),
    pipeline: IngestionPipeline = Depends(get_pipeline)
):
    logger.info("Handling request", extra={"path": request.url.path, "method": request.method, "upload_filename": file.filename})
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        # Hijack pipeline components to execute single extraction step
        old_ext = pipeline.ingestor.extractor
        pipeline.ingestor.extractor = pipeline.extractor
        documents = pipeline.ingestor.ingest(tmp_path)
        pipeline.ingestor.extractor = old_ext
    finally:
        tmp_path.unlink(missing_ok=True)

    if not documents:
        raise HTTPException(status_code=422, detail="Could not parse document")

    doc = documents[0]
    
    if vs.count() == 0 or not doc.extracted_json:
        return {
            "document": {"filename": file.filename, "extractedText": doc.text, "extractedJson": doc.extracted_json},
            "matches": [],
        }

    prompt_inputs = prepare_gap_analysis_inputs(doc.extracted_json, vs)

    by_doc: dict[str, dict] = {}
    for pi in prompt_inputs:
        doc_title = pi["existing_document_title"]
        if doc_title == "No match found":
            continue
        if doc_title not in by_doc:
            by_doc[doc_title] = {"scores": [], "content": []}
            
        by_doc[doc_title]["scores"].append(pi["similarity"])
        
        story_text = f"**{pi['new_story_title']}** (Similarity: {pi['similarity']}%)\n"
        for ac in pi["existing_acceptance_criteria"]:
            story_text += f"{ac.get('id', '')}: {ac.get('title', '')} — {ac.get('criteria', '')}\n"
        by_doc[doc_title]["content"].append(story_text)

    matches = []
    for doc_title, data in by_doc.items():
        avg_score = sum(data["scores"]) / len(data["scores"])
        matches.append(
            {
                "id": str(uuid.uuid4()),
                "documentId": doc_title,
                "documentTitle": doc_title,
                "content": "\n\n".join(data["content"]),
                "similarityScore": round(avg_score / 100.0, 3) 
            }
        )

    matches.sort(key=lambda x: -x["similarityScore"])

    return {
        "document": {"filename": file.filename, "extractedText": doc.text, "extractedJson": doc.extracted_json},
        "matches": matches[:3],
    }

@router.post("/compare")
def compare_documents(
    request: Request,
    req: CompareRequest,
    settings=Depends(get_settings),
    llm=Depends(get_llm)
):
    logger.info("Handling request", extra={"path": request.url.path, "method": request.method})
    segments = _CHUNK_PATTERN.split(req.uploadedText)
    uploaded_chunks: list[dict] = []
    current_us = "Unknown US"
    for i in range(1, len(segments), 2):
        header = segments[i].strip().replace("**", "")
        content = segments[i + 1].strip() if i + 1 < len(segments) else ""
        if "US-" in header:
            current_us = header
        uploaded_chunks.append(
            {"id": header, "header": header, "parent": current_us, "text": content}
        )

    all_kb_text = "\n\n".join(m.get("content", "") for m in req.matches)
    avg_similarity = (
        mean(m.get("similarityScore", 0.0) for m in req.matches) if req.matches else 0.0
    )

    sections = []
    gaps = []

    if uploaded_chunks:
        for chunk in uploaded_chunks:
            in_kb = chunk["header"].lower() in all_kb_text.lower()
            match_type = "uploaded_only"
            kb_content = ""

            if in_kb:
                for m in req.matches:
                    kb_text = m.get("content", "")
                    idx = kb_text.lower().find(chunk["header"].lower())
                    if idx != -1:
                        kb_content = kb_text[max(0, idx - 50): idx + len(chunk["text"]) + 300].strip()
                        match_type = "different" if kb_content.strip() != chunk["text"].strip() else "matched"
                        break

            sections.append(
                {
                    "id": f"sec-{chunk['id']}",
                    "label": chunk["header"],
                    "knowledgeBaseContent": kb_content,
                    "uploadedContent": chunk["text"],
                    "matchType": match_type,
                }
            )

            if match_type == "uploaded_only":
                gaps.append(
                    {
                        "id": f"gap-{chunk['id']}",
                        "description": f"{chunk['id']} not found in knowledge base",
                        "uploadedExcerpt": chunk["text"][:200],
                        "suggestedContext": chunk["parent"],
                    }
                )
    else:
        sections.append(
            {
                "id": "sec-full",
                "label": "Document",
                "knowledgeBaseContent": req.matches[0]["content"] if req.matches else "",
                "uploadedContent": req.uploadedText[:3000],
                "matchType": "different" if req.matches else "uploaded_only",
            }
        )

    gap_analysis_json = None
    if req.matches:
        try:
            new_title = "Uploaded Document"
            existing_title = Path(req.matches[0]["documentTitle"]).name
            
            if req.extractedJson:
                all_acs = [
                    {
                        "id": ac.get("id", ""),
                        "header": ac.get("id", ""),
                        "parent": story.get("id", ""),
                        "text": ac.get("criteria", ""),
                        "title": ac.get("title", ""),
                    }
                    for story in req.extractedJson.get("stories", [])
                    for ac in story.get("acceptance_criteria", [])
                ]
                acs_to_send = json.dumps(all_acs, indent=2) if all_acs else req.uploadedText[:8000]
            else:
                only_acs = [c for c in uploaded_chunks if "AC-" in c["header"]]
                acs_to_send = json.dumps(only_acs, indent=2) if only_acs else req.uploadedText[:8000]
            
            kb_acs_only = "\n".join(line for line in all_kb_text.split("\n") if not line.strip().startswith("**"))
            
            from src.rag_ingest.prompts import load_prompt, GAP_ANALYSIS_PROMPT
            gap_prompt_string = load_prompt(GAP_ANALYSIS_PROMPT)
            
            formatted_prompt = gap_prompt_string.replace(
                "{new_document_title}", new_title
            ).replace(
                "{new_acceptance_criteria}", acs_to_send
            ).replace(
                "{existing_document_title}", existing_title
            ).replace(
                "{existing_acceptance_criteria}", kb_acs_only[:8000]
            )

            gap_analysis_json = json.loads(llm.complete(formatted_prompt, "Please analyze the gap."))
            gap_analysis_json["new_document_title"] = new_title
            gap_analysis_json["existing_document_title"] = existing_title
            
        except Exception as e:
            print(f"LLM Gap Analysis failed: {e}")

    return {
        "overallSimilarity": round(avg_similarity, 3),
        "sections": sections,
        "gaps": gaps,
        "gapAnalysisJson": gap_analysis_json,
    }
