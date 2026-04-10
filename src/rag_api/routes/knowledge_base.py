"""Knowledge Base module for Document Gap Analysis pipeline."""
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile, BackgroundTasks, Depends, Request
import logging

from src.rag_api.services.metadata import load_meta, save_meta, UPLOADS_DIR
from src.rag_api.dependencies import get_vector_store, get_pipeline
from src.rag_ingest.store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])

def _process_upload_task(file_id: str, dest: Path, original_filename: str):
    def update_progress(msg: str):
        meta = load_meta()
        if file_id not in meta.get("files", {}):
            raise RuntimeError(f"Upload aborted: {file_id}")
        meta["files"][file_id]["status"] = msg
        save_meta(meta)

    # Lazily fetch the pipeline dependencies here because it's in a background task thread
    pipeline = get_pipeline()

    try:
        pipeline.run(dest, on_status=update_progress)
    except Exception as e:
        print(f"[KB upload] ERROR for {dest.name}: {e}")

@router.get("")
def list_kb_files(request: Request):
    logger.info("Handling request", extra={"path": request.url.path, "method": request.method})
    meta = load_meta()
    return [
        {k: v for k, v in entry.items() if k != "path"}
        for entry in meta.get("files", {}).values()
    ]

@router.post("/upload")
async def upload_kb_files(
    request: Request,
    background_tasks: BackgroundTasks, 
    files: list[UploadFile] = File(...)
):
    filenames = [f.filename for f in files]
    logger.info("Handling request", extra={"path": request.url.path, "method": request.method, "upload_filename": str(filenames)})
    meta = load_meta()
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
        if "files" not in meta:
            meta["files"] = {}
        meta["files"][file_id] = entry
        save_meta(meta)
        results.append({k: v for k, v in entry.items() if k != "path"})
        
        background_tasks.add_task(_process_upload_task, file_id, dest, upload.filename)

    return results

@router.delete("/{file_id}", status_code=204)
def delete_kb_file(request: Request, file_id: str, vs: VectorStore = Depends(get_vector_store)):
    logger.info("Handling request", extra={"path": request.url.path, "method": request.method})
    meta = load_meta()
    entry = meta.get("files", {}).get(file_id)
    if not entry:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        vs.delete_by_source(entry["path"])
    except Exception as e:
        print(f"Error during vector db delete for {file_id}: {e}")

    path = Path(entry["path"])
    if path.exists():
        path.unlink()

    del meta["files"][file_id]
    save_meta(meta)
