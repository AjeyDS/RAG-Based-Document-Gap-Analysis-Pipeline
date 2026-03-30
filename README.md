# RAG-Based Document Gap Analysis Pipeline

An end-to-end pipeline for ingesting, comparing, and analyzing gaps between Business Requirements Documents (BRDs), User Stories, and existing Knowledge Bases using Retrieval-Augmented Generation (RAG).

## 🚀 Features

- **Document Ingestion**: Uses `docling` to extract structured representations from PDF, DOCX, MD, and more.
- **Hierarchical Chunking**: Intelligently segments documents into User Stories (US) and Acceptance Criteria (AC).
- **Vector Search**: Leverages ChromaDB for semantic search and finding relevant context in existing documentation.
- **LLM Gap Analysis**: Powered by GPT-4o to identify specific gaps, missing requirements, and inconsistencies.
- **Interactive Dashboard**: A modern React frontend to visualize comparisons, scores, and AI-generated insights.

## 🛠️ Architecture

- **Backend**: Python 3.x, FastAPI, ChromaDB, OpenAI API, Docling.
- **Frontend**: React, TypeScript, Vite, Tailwind CSS.

---

## 📦 Getting Started

### 1. Prerequisites

- Python 3.10+
- Node.js 18+
- OpenAI API Key

### 2. Backend Setup

1. Create a `.env` file in the root directory:
   ```env
   OPENAI_API_KEY=your_key_here
   LLM_MODEL=gpt-4o
   ```
2. Install dependencies:
   ```bash
   pip install -e .
   ```
3. Run the API:
   ```bash
   python -m uvicorn src.rag_api.main:app --reload --port 8000
   ```

### 3. Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```

---

## 📖 Usage

1. **Upload to Knowledge Base**: Use the "Knowledge Base" tab in the UI to upload existing documentation (e.g., existing BRDs or system specs).
2. **Analyze New Document**: Upload a new BRD or User Story document on the main dashboard.
3. **Review Gaps**: The system will automatically find relevant sections in the KB and use the LLM to highlight gaps, providing a side-by-side comparison.

---

## 🏗️ Project Structure

- `src/rag_api/`: FastAPI application and endpoints.
- `src/rag_ingest/`: Core ingestion, extraction, and vector store logic.
- `frontend/`: React frontend application.
- `data/`: Local storage for uploaded files and vector database (gitignored).

---

## 🛠️ Development

### Running Tests
```bash
pytest tests/
```

### Manual Ingestion CLI
```bash
python -m rag_ingest ingest [path_to_file_or_dir] --output [output_path]
```
