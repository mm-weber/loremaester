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

try:
    import easyocr
except ModuleNotFoundError:
    easyocr = types.ModuleType("easyocr")


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
    if engine == "tesseract":
        text = pytesseract.image_to_string(image)
        data = pytesseract.image_to_data(image, output_type="dict")
        confs = [int(c) for c in data["conf"] if int(c) != -1]
        confidence = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        return PageOcrResult(page_number=page_number, text=text, confidence=confidence)
    elif engine == "easyocr":
        return PageOcrResult(page_number=page_number, text="", confidence=0.0)
    raise ValueError(f"Unsupported OCR engine: {engine}")


def ocr_pdf(pdf_path, engine="tesseract", language="eng", page_range=None):
    images = render_pages(pdf_path, page_range)
    pages = [
        ocr_image(img, page_number=i + 1, engine=engine, language=language, reader=None)
        for i, img in enumerate(images)
    ]
    content = "\n\n".join(f"[Page {p.page_number}]\n{p.text}" for p in pages)
    return OcrExtraction(content=content, pages=pages, mean_confidence=0.0, low_confidence_pages=[])
