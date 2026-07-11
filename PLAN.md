# receipt — Plan

A personal, offline app to scan receipts, extract their text with on-device OCR,
store everything locally, and search across all receipts by text (e.g. search
"IKEA" → see every scanned receipt containing that word).

## Context

The user wants a private receipt vault. The core need is *find a receipt later by
what's written on it*. Everything stays on the user's machine — no cloud, no
accounts. Receipts are printed (not handwritten), so a lightweight on-device OCR
engine (RapidOCR / PaddleOCR) is sufficient and was chosen deliberately over a
cloud vision model.

## What it does (user flow)

1. **Add a receipt** — upload or drag-drop a photo/scan (JPG/PNG/PDF).
2. **OCR** — the app runs RapidOCR on the image, extracts all text.
3. **Store** — the original image is saved to a local folder; the extracted text
   + metadata go into a local SQLite database, indexed for search.
4. **Search** — a search box; typing `IKEA` returns all receipts whose text
   contains "IKEA", each shown as a thumbnail + snippet + date. Click to open the
   full image.

## Architecture

A **local web app**: a small Python backend that also serves a simple browser UI.
The user runs one command, opens `http://localhost:8000`, and uses it in the
browser. This keeps the Python OCR engine and the storage together, works on
Windows/Mac/Linux, and needs no packaging into a native binary.

```
Browser UI  ──HTTP──►  FastAPI backend  ──►  RapidOCR (ONNX)  → text
(upload/search)                          ──►  images/  (original files on disk)
                                         ──►  receipts.db (SQLite + FTS5)
```

> Confirmed: **local web app** (browser UI on localhost). Scope for the first
> build is **plain text search only** — no structured merchant/total/date parsing
> yet (deferred to Phase 3).

## Tech stack

| Concern    | Choice | Why |
|------------|--------|-----|
| Language   | Python 3.11+ | Required by RapidOCR/PaddleOCR |
| OCR        | **RapidOCR** (`rapidocr-onnxruntime`) | ~80 MB, ONNX, no PaddlePaddle dependency, CPU-only, offline. PaddleOCR is the drop-in alternative if you want its fuller model zoo. |
| Backend/API| **FastAPI** + Uvicorn | Tiny, async file uploads, serves the UI too |
| Storage    | **SQLite** with **FTS5** | Single local file = the "local storage"; built-in fast full-text search |
| Images     | Saved to a local `data/images/` folder | Keeps the DB small; DB stores the path |
| Frontend   | Plain HTML + a little vanilla JS (or HTMX) | Two screens; no build step needed |
| Preprocess | Pillow / OpenCV (optional) | Grayscale + deskew to lift OCR accuracy on phone photos |

## Data model

SQLite, two tables:

```sql
-- one row per receipt
CREATE TABLE receipts (
  id          INTEGER PRIMARY KEY,
  image_path  TEXT NOT NULL,        -- data/images/<uuid>.jpg
  ocr_text    TEXT NOT NULL,        -- full extracted text
  created_at  TEXT NOT NULL,        -- ISO timestamp
  merchant    TEXT,                 -- optional: best-guess from first lines
  total       TEXT                  -- optional: parsed amount
);

-- full-text search index over the receipt text (+ merchant)
CREATE VIRTUAL TABLE receipts_fts USING fts5(
  ocr_text, merchant, content='receipts', content_rowid='id'
);
```

Triggers keep `receipts_fts` in sync on insert/update/delete (standard FTS5
external-content pattern).

## Search design

- Query: `SELECT ... FROM receipts_fts WHERE receipts_fts MATCH ? ORDER BY rank`.
- Typing `IKEA` matches receipts containing the token "IKEA" (case-insensitive),
  ranked by relevance — exactly the requested behavior.
- FTS5's `snippet()` / `highlight()` produces the matched-text preview shown in
  results.
- Substring fallback (`LIKE '%ikea%'`) available for partial words if desired.

## OCR pipeline (backend)

1. Save upload to `data/images/<uuid>.<ext>`.
2. (Optional) preprocess: grayscale, auto-rotate/deskew.
3. `result = rapidocr(image)` → join detected text lines into one string.
4. (Optional light parsing) guess `merchant` from the top lines and `total` via a
   currency regex — nice-to-have, not required for search.
5. `INSERT` into `receipts`; FTS index updates via trigger.

## Screens

1. **Add** — drop zone + "Add receipt" button; shows a spinner during OCR, then a
   confirmation with the extracted text preview.
2. **Search** — a search box + results list (thumbnail, merchant/date, snippet).
   Clicking a result opens the full-size image and full text.

## Build phases

- **Phase 1 — MVP (core loop):** FastAPI app; upload endpoint → RapidOCR → store
  in SQLite; search endpoint using FTS5; minimal two-page UI. Delivers the whole
  requested experience end-to-end.
- **Phase 2 — quality:** image preprocessing for better OCR, snippet highlighting
  in results, thumbnails, delete/re-OCR a receipt.
- **Phase 3 — nice-to-haves:** merchant/total/date parsing and filters, PDF
  support, export, tagging.

## Project layout

```
receipt/
  app/
    main.py          # FastAPI app + routes (/, /add, /search)
    ocr.py           # RapidOCR wrapper + preprocessing
    db.py            # SQLite connection, schema, FTS queries
    templates/       # add.html, search.html
    static/          # css/js
  data/
    images/          # stored receipt images (gitignored)
    receipts.db      # SQLite database (gitignored)
  requirements.txt
  README.md
```

## Verification (how we'll test it works)

1. `pip install -r requirements.txt && uvicorn app.main:app` → open localhost.
2. Upload a real IKEA receipt image → confirm the response shows extracted text
   including "IKEA".
3. Upload 2–3 other receipts.
4. Search `IKEA` → only the IKEA receipt(s) return; search a word unique to
   another receipt → only that one returns.
5. Restart the app → data persists (proves local storage).
6. Confirm it works with the network disconnected (proves fully offline).

## Decisions & open questions

- **Platform:** local web app (browser UI on localhost). ✅ Confirmed.
- **Scope:** plain text search only for the first build; merchant/total/date
  parsing deferred to Phase 3. ✅ Confirmed.
- **PDF receipts:** open — images only for now unless you need PDF support too.
