# receipt

A private, **offline** receipt vault. Scan a receipt, and its text is extracted
on your own machine with OCR and stored locally. Later, search across every
receipt by text — type `IKEA` and get back every receipt that mentions it.

Nothing leaves your computer: no cloud, no account. Images live in a local
folder and the text is indexed in a local SQLite database.

## How it works

1. **Add** a receipt image (JPG/PNG/WEBP) on the *Add* page.
2. It's OCR'd locally with [RapidOCR](https://github.com/RapidAI/RapidOCR)
   (ONNX Runtime, CPU-only).
3. The original image is saved to `data/images/` and the extracted text is
   stored in `data/receipts.db`.
4. **Search** from the home page. Matching uses SQLite's FTS5 full-text index,
   so it's fast and ranked, with highlighted snippets.

## Requirements

- Python 3.11+

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app          # add --reload while developing
```

Then open <http://localhost:8000>.

The first scan takes a few extra seconds while the OCR model loads; after that
it's quick.

## Project layout

```
app/
  main.py       # FastAPI routes + UI
  ocr.py        # RapidOCR wrapper
  db.py         # SQLite + FTS5 storage and search
  config.py     # local paths
  templates/    # search / add / receipt pages
  static/       # stylesheet
data/           # your images + database (created on first run, gitignored)
```

## Notes & limits

- Tuned for **printed** receipts. Crumpled or dim phone photos read less well;
  image preprocessing (deskew/grayscale) is a planned improvement.
- Currently image files only (no PDF) and plain text search only — structured
  fields like merchant/total/date are a future addition. See `PLAN.md`.
