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

from rag_ingest.ingest import Ingestor
from rag_ingest.extractor import LLMExtractor
from rag_ingest.chunking import chunk_document
from rag_ingest.store import VectorStore

# ── paths ─────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
from gap_analysis_prompt import GAP_ANALYSIS_PROMPT

DATA_DIR = _ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads" / "kb"
CHROMA_DIR = DATA_DIR / "chroma_db"
META_FILE = DATA_DIR / "kb_metadata.json"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

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
        _vs = VectorStore(persist_dir=CHROMA_DIR)
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
        for doc in documents:
            if doc.extracted_json is None:
                raise ValueError(f"LLM extraction produced no JSON for {dest.name}")
            update_progress("chunking")
            import time; time.sleep(1.5)
            chunks_result = chunk_document(doc.extracted_json)
            update_progress("embedding")
            time.sleep(1.5)
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
    except Exception:
        pass

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
        documents = Ingestor().ingest(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not documents:
        raise HTTPException(status_code=422, detail="Could not parse document")

    doc = documents[0]

    # KB may be empty or document may fail to produce any text.
    # `doc.chunks` is not populated in this endpoint (chunking is for the KB).
    if vs.count() == 0 or not doc.text:
        return {
            "document": {"filename": file.filename, "extractedText": doc.text},
            "matches": [],
        }

    # Query KB with the full text; group best-scoring chunk per source
    hits = vs.query(doc.text[:8000], n_results=min(10, vs.count()))
    by_source: dict[str, float] = {}
    for hit in hits:
        score = 1.0 - hit["distance"]
        src = hit["source"]
        if src not in by_source or score > by_source[src]:
            by_source[src] = score

    matches = []
    for src, score in sorted(by_source.items(), key=lambda x: -x[1])[:3]:
        chunks = vs.get_chunks_by_source(src)
        content = "\n\n".join(c["text"] for c in chunks[:15])
        matches.append(
            {
                "id": str(uuid.uuid4()),
                "documentId": src,
                "documentTitle": Path(src).name,
                "content": content,
                "similarityScore": round(score, 3),
            }
        )

    return {
        "document": {"filename": file.filename, "extractedText": doc.text},
        "matches": matches,
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
            
            acs_to_send = json.dumps(uploaded_chunks, indent=2) if uploaded_chunks else req.uploadedText[:8000]
            
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
