from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.rag_ingest.ingest import Ingestor
from src.rag_ingest.extractor import LLMExtractor
from src.rag_ingest.chunking import chunk_for_storage
from src.rag_ingest.store import VectorStore

# ── story-level retrieval ─────────────────────────────────────────────────────
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
        
        # In the new schema, chunk_id is used. 
        # But for criteria search, we use story_id which is the suffix after scope
        full_story_id = best["id"] # This is the chunk_id from story
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

# ── paths ─────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
from gap_analysis_prompt import GAP_ANALYSIS_PROMPT

DATA_DIR = _ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads" / "kb"
META_FILE = DATA_DIR / "kb_metadata.json"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

_CHUNK_PATTERN = re.compile(r"(\*\*US-\d+\.\d+.*?\*\*|\*\*AC-\d+\.\d+.*?\*\*)")

# ── app ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── metadata store (simple JSON file) ─────────────────────────────────────────
def _load_meta() -> dict:
    if META_FILE.exists():
        return json.loads(META_FILE.read_text())
    return {"files": {}}


def _save_meta(meta: dict) -> None:
    META_FILE.parent.mkdir(parents=True, exist_ok=True)
    META_FILE.write_text(json.dumps(meta, indent=2))


# ── VectorStore singleton ──────────────────────────────────────────────────────
_vs: VectorStore | None = None


def _get_vs() -> VectorStore:
    global _vs
    if _vs is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
             raise ValueError("DATABASE_URL not found in .env")
        _vs = VectorStore(db_url=db_url)
    return _vs


# ── request models ─────────────────────────────────────────────────────────────
class CompareRequest(BaseModel):
    uploadedText: str
    matches: list[dict]


class GapGenerateRequest(BaseModel):
    gapId: str
    source: str


# ── knowledge base endpoints ───────────────────────────────────────────────────
@app.get("/api/knowledge-base")
def list_kb_files():
    meta = _load_meta()
    return [
        {k: v for k, v in entry.items() if k != "path"}
        for entry in meta["files"].values()
    ]


def _process_upload_task(file_id: str, dest: Path, original_filename: str):
    def update_progress(msg: str):
        meta = _load_meta()
        if file_id in meta["files"]:
            meta["files"][file_id]["status"] = msg
            _save_meta(meta)

    update_progress("processing")
    vs = _get_vs()
    extractor = LLMExtractor(
        model=os.environ.get("LLM_MODEL", "gpt-4o"),
        prompt_path=str(_ROOT / "ingestion_prompt.py"),
    )
    ingestor = Ingestor(extractor=extractor, progress_cb=update_progress)

    try:
        documents = ingestor.ingest(dest)
        
        if file_id not in _load_meta().get("files", {}):
            return  # abort if deleted early
            
        for doc in documents:
            if doc.extracted_json is None:
                raise ValueError(f"LLM extraction produced no JSON for {dest.name}")
            update_progress("chunking")
            chunks_result = chunk_for_storage(doc.extracted_json)
            update_progress("embedding")
            
            if file_id not in _load_meta().get("files", {}):
                return  # abort before writing to vs
            
            vs.add_document_chunks(chunks_result, source_path=str(dest))
        update_progress("ready")
    except Exception as e:
        update_progress("error")
        print(f"[KB upload] ERROR for {dest.name}: {e}")

@app.post("/api/knowledge-base/upload")
async def upload_kb_files(background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)):
    meta = _load_meta()
    results = []

    for upload in files:
        file_id = str(uuid.uuid4())
        dest = UPLOADS_DIR / f"{file_id}_{upload.filename}"
        dest.write_bytes(await upload.read())

        status = "processing"
        entry = {
            "id": file_id,
            "filename": upload.filename,
            "uploadedAt": datetime.now(timezone.utc).isoformat(),
            "sizeBytes": dest.stat().st_size,
            "status": status,
            "path": str(dest),
        }
        meta["files"][file_id] = entry
        _save_meta(meta)
        results.append({k: v for k, v in entry.items() if k != "path"})
        
        background_tasks.add_task(_process_upload_task, file_id, dest, upload.filename)

    return results


@app.delete("/api/knowledge-base/{file_id}", status_code=204)
def delete_kb_file(file_id: str):
    meta = _load_meta()
    entry = meta["files"].get(file_id)
    if not entry:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        _get_vs().delete_by_source(entry["path"])
    except Exception as e:
        print(f"Error during vector db delete for {file_id}: {e}")



    path = Path(entry["path"])
    if path.exists():
        path.unlink()

    del meta["files"][file_id]
    _save_meta(meta)


# ── document upload + KB search ────────────────────────────────────────────────
@app.post("/api/documents/upload")
async def upload_and_search(file: UploadFile = File(...)):
    vs = _get_vs()

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        extractor = LLMExtractor(
            model=os.environ.get("LLM_MODEL", "gpt-4o"),
            prompt_path=str(_ROOT / "ingestion_prompt.py"),
        )
        documents = Ingestor(extractor=extractor).ingest(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not documents:
        raise HTTPException(status_code=422, detail="Could not parse document")

    doc = documents[0]
    
    if vs.count() == 0 or not doc.extracted_json:
        return {
            "document": {"filename": file.filename, "extractedText": doc.text},
            "matches": [],
        }

    # Use the new story-level retrieval logic
    prompt_inputs = prepare_gap_analysis_inputs(doc.extracted_json, vs)

    by_doc: dict[str, dict] = {}
    for pi in prompt_inputs:
        doc_title = pi["existing_document_title"]
        if doc_title == "No match found":
            continue
        if doc_title not in by_doc:
            by_doc[doc_title] = {"scores": [], "content": []}
            
        by_doc[doc_title]["scores"].append(pi["similarity"])
        
        # Build structured content string for the frontend and LLM
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
                # Join the contents
                "content": "\n\n".join(data["content"]),
                # Frontend expects max 1
                "similarityScore": round(avg_score / 100.0, 3) 
            }
        )

    # Sort dynamically
    matches.sort(key=lambda x: -x["similarityScore"])

    return {
        "document": {"filename": file.filename, "extractedText": doc.text},
        "matches": matches[:3], 
    }


# ── comparison ─────────────────────────────────────────────────────────────────
@app.post("/api/documents/compare")
def compare_documents(req: CompareRequest):
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
        # No US/AC chunks — return whole-document section
        sections.append(
            {
                "id": "sec-full",
                "label": "Document",
                "knowledgeBaseContent": req.matches[0]["content"] if req.matches else "",
                "uploadedContent": req.uploadedText[:3000],
                "matchType": "different" if req.matches else "uploaded_only",
            }
        )

    # ── LLM Gap Analysis ────────────────────────────────────────────────────────
    gap_analysis_json = None
    if req.matches:
        try:
            from openai import OpenAI
            client = OpenAI()
            new_title = "Uploaded Document"
            existing_title = Path(req.matches[0]["documentTitle"]).name
            
            only_acs = [c for c in uploaded_chunks if "AC-" in c["header"]]
            acs_to_send = json.dumps(only_acs, indent=2) if only_acs else req.uploadedText[:8000]
            
            formatted_prompt = GAP_ANALYSIS_PROMPT.replace(
                "{new_document_title}", new_title
            ).replace(
                "{new_acceptance_criteria}", acs_to_send
            ).replace(
                "{existing_document_title}", existing_title
            ).replace(
                "{existing_acceptance_criteria}", all_kb_text[:8000]
            )

            res = client.chat.completions.create(
                model=os.environ.get("LLM_MODEL", "gpt-4o"),
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": formatted_prompt}],
                temperature=0.1
            )
            gap_analysis_json = json.loads(res.choices[0].message.content)
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


# ── gap generation (stub) ──────────────────────────────────────────────────────
@app.post("/api/gaps/generate")
def generate_gap(req: GapGenerateRequest):
    return {
        "content": f"[Placeholder: generated content for '{req.gapId}' via {req.source} — LLM integration coming soon]"
    }
