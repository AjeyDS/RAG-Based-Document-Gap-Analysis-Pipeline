# Document Comparison Frontend

React + Vite + TypeScript frontend for comparing BRDs and user story documents against a knowledge base.

## Setup

```sh
npm install
```

## Development

```sh
npm run dev
```

Opens at [http://localhost:5173](http://localhost:5173).

## Build

```sh
npm run build
```

Output in `dist/`.

## Environment

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API base URL (e.g. `http://localhost:8000`). When unset, mock data is used. |
| `VITE_USE_MOCK` | Set to `"false"` to disable mock and use real API. |

## Backend Integration

When the backend is ready, set `VITE_API_URL` to your API base. Expected endpoints:

- `POST /api/documents/upload` — multipart file upload, returns `{ document, matches }`
- `POST /api/documents/compare` — `{ uploadedText, matches }` → `ComparisonResult`
- `POST /api/gaps/generate` — `{ gapId, source }` → `{ content }`
