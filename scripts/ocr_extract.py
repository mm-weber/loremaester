# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pypdfium2",
#   "pytesseract",
#   "Pillow",
#   "r2r",
# ]
# ///
"""Per-page OCR extraction for scanned PDFs."""
from dataclasses import dataclass, field
import types

try:
    import pypdfium2
except ModuleNotFoundError:
    pypdfium2 = types.ModuleType("pypdfium2")

try:
    import pytesseract
except ModuleNotFoundError:
    pytesseract = types.ModuleType("pytesseract")


@dataclass
class PageOcrResult:
    page_number: int
    text: str
    confidence: float


@dataclass
class OcrExtraction:
    content: str
    pages: list
    mean_confidence: float
    low_confidence_pages: list = field(default_factory=list)


def render_pages(pdf_path, page_range=None):
    return []


def ocr_image(image, page_number=1, engine="tesseract", language="eng", reader=None):
    return None


def ocr_pdf(pdf_path, engine="tesseract", language="eng", page_range=None):
    return OcrExtraction(content="", pages=[], mean_confidence=0.0, low_confidence_pages=[])
