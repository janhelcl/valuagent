# valuagent

Simple API to extract and validate Czech financial statements (Rozvaha, Výkaz zisku a ztráty) from annual-report PDFs using an LLM. Produces validated JSON and an Excel workbook.

## Run locally

1) Install deps (Poetry):

```bash
poetry install
```

2) Set env vars (use your key and desired model):

```bash
set GOOGLE_API_KEY=your_key_here
set GENAI_MODEL=gemini-2.5-pro
```

3) Start the API:

```bash
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

(Alternatively for backward compatibility: `poetry run uvicorn src.server:app --reload --host 0.0.0.0 --port 8000`)

4) Open in browser: http://localhost:8000 and upload a PDF.

## API

- `GET /` simple upload form
- `POST /process` (multipart): `pdf`, `statement_type` (`rozvaha|vzz`), `year`, `tolerance`, optional `return_json=true`

## Notes

- JSON is validated with Pydantic models in `src/domain/models` (split into `balance_sheet.py`, `profit_and_loss.py`, and `rules.py`). Excel export includes a validation report sheet.