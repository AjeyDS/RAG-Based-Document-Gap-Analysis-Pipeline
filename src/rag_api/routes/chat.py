"""Chat route for RAG-powered conversational queries against the knowledge base."""
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.rag_api.dependencies import get_current_user, get_vector_store, get_llm
from src.rag_ingest.store import VectorStore
from src.rag_ingest.prompts.chat_prompt import CHAT_PROMPT
from src.rag_ingest.exceptions import LLMExtractionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


@router.post("")
def chat_with_kb(
    request: Request,
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
    vs: VectorStore = Depends(get_vector_store),
    llm=Depends(get_llm),
) -> dict:
    """Query the knowledge base conversationally and return an answer with source citations."""
    logger.info(
        "Handling chat request",
        extra={"path": request.url.path, "user_id": current_user.get("user_id")},
    )

    matched_chunks = vs.query_all_chunks(req.message, top_k=5)

    context_blocks: list[str] = []
    sources: list[dict] = []
    # Per-request cache to avoid redundant DB lookups for the same parent story.
    story_meta_cache: dict[str, dict] = {}

    for chunk in matched_chunks:
        metadata = chunk.get("metadata", {}) or {}
        chunk_type = chunk.get("chunk_type", "unknown")
        ac_title = metadata.get("ac_title", "")

        if ac_title == "NA":
            logger.warning("Source chunk has ac_title='NA' (ingestion data issue)", extra={"chunk_id": chunk.get("id")})

        if chunk_type == "criteria":
            story_id = chunk.get("story_id", "")
            if story_id not in story_meta_cache:
                story_meta_cache[story_id] = vs.get_story_metadata(story_id) or {}
            parent_meta = story_meta_cache[story_id]
            story_title = parent_meta.get(
                "story_title",
                metadata.get("story_id_original") or story_id or "Unknown Story",
            )
        else:
            story_title = metadata.get("story_title", "Unknown Story")

        source_path = chunk.get("source", "")
        filename = Path(source_path).name
        doc_title = filename.split("_", 1)[-1] if "_" in filename else filename
        chunk_content = chunk.get("document", "")
        distance = chunk.get("distance")
        similarity = round(max(0.0, 1.0 - distance), 3) if distance is not None else 0.0

        context_blocks.append(
            f"Document: {doc_title}\n"
            f"Story: {story_title}\n"
            f"{'Criteria: ' + ac_title if ac_title else ''}\n"
            f"Content: {chunk_content}\n"
        )
        sources.append({
            "story_title": story_title,
            "ac_title": ac_title if ac_title else story_title,
            "content": chunk_content[:200] + "..." if len(chunk_content) > 200 else chunk_content,
            "document_title": doc_title,
            "similarity_score": similarity,
            "chunk_type": chunk_type,
        })

    context_text = "\n---\n".join(context_blocks)
    formatted_prompt = CHAT_PROMPT.replace("{context}", context_text).replace("{question}", req.message)

    try:
        if hasattr(llm, "complete_text"):
            answer = llm.complete_text(formatted_prompt, "Please answer in plain text.")
        else:
            # complete() returns raw text; ask for JSON so we can extract a clean answer string
            j_prompt = formatted_prompt + "\n\nProvide your response as a valid JSON object with a single key 'answer'."
            raw_answer = llm.complete(j_prompt, "Please return JSON with the answer.")
            try:
                answer = json.loads(raw_answer).get("answer", raw_answer)
            except json.JSONDecodeError:
                answer = raw_answer
    except Exception as e:
        logger.error("Chat LLM failed: %s", e)
        raise LLMExtractionError(f"Chat generation failed: {e}") from e

    return {"answer": answer, "sources": sources}
