"""receipt — a local, offline receipt vault with OCR full-text search.

Run:  uvicorn app.main:app --reload
Then open http://localhost:8000
"""
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db
from .config import ALLOWED_EXTENSIONS, IMAGES_DIR, ensure_dirs
from .ocr import extract_text


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create the local data folder + database on startup
    ensure_dirs()
    db.init_db()
    yield


app = FastAPI(title="receipt", lifespan=lifespan)

APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def search_page(request: Request, q: str = ""):
    """Search screen. With a query, show matches; otherwise show recent receipts."""
    query = q.strip()
    if query:
        results = db.search_receipts(query)
    else:
        results = db.list_receipts()
    return templates.TemplateResponse(
        request,
        "search.html",
        {
            "q": query,
            "results": results,
            "total": db.count_receipts(),
        },
    )


@app.get("/add", response_class=HTMLResponse)
def add_page(request: Request):
    return templates.TemplateResponse(request, "add.html", {"error": None})


@app.post("/add", response_class=HTMLResponse)
async def add_receipt(request: Request, file: UploadFile = File(...)):
    """Save the uploaded image, OCR it, and store the text for searching."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return templates.TemplateResponse(
            request,
            "add.html",
            {
                "error": f"Unsupported file type '{suffix}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            },
            status_code=400,
        )

    stored_name = f"{uuid.uuid4().hex}{suffix}"
    dest = IMAGES_DIR / stored_name
    dest.write_bytes(await file.read())

    text = extract_text(str(dest))
    receipt_id = db.add_receipt(
        image_path=stored_name, filename=file.filename or stored_name, ocr_text=text
    )
    return RedirectResponse(url=f"/receipt/{receipt_id}", status_code=303)


@app.get("/receipt/{receipt_id}", response_class=HTMLResponse)
def receipt_detail(request: Request, receipt_id: int):
    receipt = db.get_receipt(receipt_id)
    if not receipt:
        return HTMLResponse("Receipt not found", status_code=404)
    return templates.TemplateResponse(
        request, "receipt.html", {"receipt": receipt}
    )


@app.get("/image/{receipt_id}")
def receipt_image(receipt_id: int):
    """Serve the stored image for a receipt."""
    receipt = db.get_receipt(receipt_id)
    if not receipt:
        return HTMLResponse("Not found", status_code=404)
    path = IMAGES_DIR / receipt["image_path"]
    if not path.exists():
        return HTMLResponse("Image missing", status_code=404)
    return FileResponse(str(path))
