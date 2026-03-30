# Document Comparison Frontend

React + Vite + TypeScript frontend for comparing BRDs and User Story documents against a Knowledge Base.

## 🚀 Features

- **Knowledge Base Management**: Side-tab for uploading/viewing documents in the persistent KB.
- **Document Comparison View**: Side-by-side comparison between uploaded text and KB matches.
- **AI Gap Analysis Dashboard**: Structured overview of missing requirements and inconsistencies.
- **Mock Mode**: Fully interactive UI even without the backend API (configurable).

---

## 🛠️ Getting Started

### 1. Install Dependencies

```bash
npm install
```

### 2. Development Mode

Runs the development server with Hot Module Replacement (HMR).

```bash
npm run dev
```

Opens at [http://localhost:5173](http://localhost:5173).

### 3. Build for Production

```bash
npm run build
```

The build artifacts will be stored in the `dist/` directory.

---

## ⚙️ Configuration

Create a `.env` file in the `frontend/` directory (optional):

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API base URL (e.g. `http://localhost:8000`). |
| `VITE_USE_MOCK` | Set to `"true"` to force mock data, or `"false"` to only use real API. |

---

## 🧩 Backend Integration

The frontend expects a FastAPI backend running at `VITE_API_URL`. Key endpoints:

- `POST /api/documents/upload`: Multipart file upload.
- `POST /api/documents/compare`: Document text and matches → `ComparisonResult`.
- `POST /api/knowledge-base/upload`: Upload files to the vector store.
- `GET /api/knowledge-base`: List current files in the store.
