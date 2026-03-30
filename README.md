# RAG Ingestion

This project ingests PDFs and documentation-style files into a structured JSON
representation using `docling`. It intentionally preserves document structure
so hierarchical chunking can happen later as a separate step.

## Supported inputs

- `.pdf`
- `.md`
- `.html`, `.htm`
- `.docx`
- `.adoc`, `.asciidoc`

Plain `.txt` files are also accepted through a tiny fallback path because
`docling` does not natively convert them.

You can ingest a single file or a directory of supported files.

## Install

```bash
python3 -m pip install -e '.[dev]'
```

## Usage

Ingest one file:

```bash
python3 -m rag_ingest ingest ./docs/guide.md --output ./artifacts/guide.json
```

Ingest a directory:

```bash
python3 -m rag_ingest ingest ./docs --output ./artifacts/corpus.json
```

Write JSON to stdout:

```bash
python3 -m rag_ingest ingest ./manual.pdf
```

## Output shape

Each ingested document includes:

- source metadata
- normalized text exported from `docling`
- a hierarchy tree

For `docling`-supported formats, the hierarchy is built from title and section
items extracted by `docling`. Plain text files are kept as a single body node.
