# Local web workbench

Start the installed workbench with:

```bash
zupulint web --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The same process serves the compiled React application and FastAPI endpoints, so Node.js is not required for end users.

## Workflow

1. Choose or drop a `.ged`, `.gedcom`, `.csv`, `.xlsx`, or `.json` file.
2. Inspect the bounded preview and parser metadata.
3. For CSV, choose encoding/delimiter and map source headers. For XLSX, choose the worksheet and map headers.
4. Optionally attach a strict YAML configuration.
5. Run the real local API scan. Stage labels reflect actual request state; there is no simulated timer.
6. Filter results by severity, rule, category, or person; expand evidence, confidence, related IDs, and suggestions.
7. Download HTML, JSON, or SARIF from the API, or clear all browser state.

The interface supports Chinese/English labels, keyboard operation, focus states, responsive layouts, dark color schemes, and reduced motion. React Router provides the workbench and privacy routes; TanStack Query owns real preview/scan/report request state.

## API endpoints

- `GET /health`, `GET /version`
- `GET /api/rules`, `GET /api/rules/{id}`
- `POST /api/preview`
- `POST /api/scan`, `POST /api/validate`, `POST /api/report?format=html|json|sarif`
- `GET /docs` for OpenAPI

Uploads are multipart form data. Optional fields are `sheet`, `delimiter`, `encoding`, `column_mapping`, and `config_file`. Errors use explicit HTTP 413/415/422 responses.

## Privacy behavior

The browser does not persist uploaded data, and a refresh does not re-upload it. The local API uses request-scoped temporary directories, disables access logging in the CLI server, and returns `Cache-Control: no-store` plus restrictive CSP, referrer, permissions, and content-type headers.
