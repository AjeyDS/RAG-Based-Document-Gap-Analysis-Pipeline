# Development Guide

This document captures underlying structural assumptions seamlessly required to effectively navigate and iteratively augment logic inside this codebase seamlessly.

## Project Structure

```text
├── docs/                        # Key architectural documentation mapping constraints
├── frontend/                    # Vite React application structuring visualization elements
├── src/
│   ├── rag_api/                 # FastAPI routes heavily controlling endpoint REST logic globally
│   │   ├── routes/              # Centralized route segment logic containing controllers securely
│   │   └── services/            # Stateless metadata tracking elements logically mapping execution
│   └── rag_ingest/              # Engine components capturing document retrieval manipulation maps
│       ├── llm/                 # Abstraction implementations natively interfacing external OpenAI resources
│       ├── exceptions.py        # Centralized explicit custom try/except mapping bounds tightly enforced
│       ├── pipeline.py          # Native functional orchestrator mapping docling chunks to vector instances
│       ├── store.py             # Active pgvector cursor transaction wrapper natively executing mapping
```

## Adding a New LLM Provider

Architectural boundaries logically support seamless API mappings substituting OpenAI boundaries.
1. Create a class inside `src/rag_ingest/llm/` implementing native representations bound by `LLMProvider` or `EmbeddingProvider` from `base.py`.
2. Construct dynamic implementations inside `src/rag_ingest/llm/factory.py` configuring active connections executing successfully relying seamlessly on `.env` tokens locally.
3. Augment application `.env` keys configuring internal bindings representing custom model nomenclature seamlessly.

## Modifying Prompts

Prompts tightly reside effectively inside `src/rag_ingest/prompts/`.
- Ensure literal mapping `{markdown_content}` natively intercepts injection placeholders reliably mapping user inputs completely gracefully.
- Recompiling modifications logically enforces re-running the test endpoints executing `curl` logic directly comparing responses internally verifying valid JSON mapping schemas properly returning `stories` explicitly.

## Key Design Decisions

- **Why `pgvector`?** Eliminates the brittle abstraction layer forced implicitly navigating separate Vector DB engines allowing unified logical CRUD commands natively wrapping existing database configurations securely.
- **Why Separate Story/AC Chunks?** Sub-segment mapping improves semantic hits internally retrieving specific constrained granular components preventing massive unlocalized chunk contamination heavily. 
- **Why `IVFFlat` indexes?** Optimized heavily explicitly handling highly dimensional datasets iteratively improving massive vector search constraint latency overhead.
- **How the Verdict Engine Works**: Raw comparisons map natively utilizing semantic bounds routing retrieved AC elements directly executing logic against the uploaded texts generating explicitly functional matched disparity arrays iteratively. 

## Common Issues

- **"LLM returns invalid JSON" (`LLMExtractionError`)** -> Model natively ignores logical formatting structures gracefully. Verify active prompts map accurately defining JSON shapes clearly relying heavily on trailing `json` prompt bindings inherently.
- **"Connection Refused" (`StorageError`)** -> Environment mappings incorrectly routing logical boundaries pointing specifically towards `localhost` natively during Docker Compose execution properly enforcing `PG_HOST=db`.
- **"Connection Timeout Error" (Frontend)** -> Typically triggered implicitly navigating unsupported node versions dynamically enforcing Vite mapping requirements locally mapping bindings properly mapping `.env` boundaries executing `3000` to `8000` bounds.
