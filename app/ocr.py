"""On-device OCR using RapidOCR (ONNX Runtime).

The engine is created lazily on first use and reused, since loading the ONNX
models takes a moment. Everything runs locally on CPU — no network required.
"""
from functools import lru_cache

from rapidocr_onnxruntime import RapidOCR


@lru_cache(maxsize=1)
def _engine() -> RapidOCR:
    return RapidOCR()


def extract_text(image_path: str) -> str:
    """Run OCR on an image file and return all detected text as one string.

    RapidOCR returns a list of [box, text, confidence] entries (or None when no
    text is found). We keep the detection order, which for receipts reads
    roughly top-to-bottom.
    """
    result, _elapse = _engine()(image_path)
    if not result:
        return ""
    lines = [entry[1] for entry in result if len(entry) >= 2 and entry[1]]
    return "\n".join(lines)
