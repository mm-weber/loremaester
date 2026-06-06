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

LOW_CONFIDENCE_THRESHOLD = 0.7
RENDER_SCALE = 2.78  # pdfium scale 1.0 = 72 dpi; 2.78 ≈ 200 dpi

try:
    import pypdfium2
    _HAS_PYPDFIUM2 = True
except ModuleNotFoundError:
    pypdfium2 = types.ModuleType("pypdfium2")
    _HAS_PYPDFIUM2 = False

try:
    import pytesseract
    _HAS_TESSERACT = True
except ModuleNotFoundError:
    pytesseract = types.ModuleType("pytesseract")
    _HAS_TESSERACT = False

try:
    import easyocr
    _HAS_EASYOCR = True
except ModuleNotFoundError:
    easyocr = types.ModuleType("easyocr")
    _HAS_EASYOCR = False


def _require(available, package, install_hint):
    pass


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


def parse_page_range(range_str):
    first, last = range_str.split("-")
    return int(first), int(last)


def render_pages(pdf_path, page_range=None):
    pdf = pypdfium2.PdfDocument(pdf_path)
    n = len(pdf)
    if page_range:
        first, last = parse_page_range(page_range)  # 1-based inclusive
        indices = range(first - 1, min(last, n))
    else:
        indices = range(n)
    return [pdf[i].render(scale=RENDER_SCALE).to_pil() for i in indices]


def ocr_image(image, page_number=1, engine="tesseract", language="eng", reader=None):
    if engine == "tesseract":
        text = pytesseract.image_to_string(image)
        data = pytesseract.image_to_data(image, output_type="dict")
        confs = [int(c) for c in data["conf"] if int(c) != -1]
        confidence = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        return PageOcrResult(page_number=page_number, text=text, confidence=confidence)
    elif engine == "easyocr":
        import io
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        results = reader.readtext(buf.getvalue(), detail=1)  # list of (bbox, text, conf)
        text = "\n".join(t for (_, t, _) in results)
        confidence = (sum(c for (_, _, c) in results) / len(results)) if results else 0.0
        return PageOcrResult(page_number=page_number, text=text, confidence=confidence)
    raise ValueError(f"Unsupported OCR engine: {engine}")


def make_reader(language="eng"):
    # easyocr auto-falls back to CPU when no CUDA device is available
    return easyocr.Reader([language], gpu=True)


def ocr_pdf(pdf_path, engine="tesseract", language="eng", page_range=None):
    images = render_pages(pdf_path, page_range)
    reader = make_reader(language) if engine == "easyocr" else None
    pages = [
        ocr_image(img, page_number=i + 1, engine=engine, language=language, reader=reader)
        for i, img in enumerate(images)
    ]
    content = "\n\n".join(f"[Page {p.page_number}]\n{p.text}" for p in pages)
    mean_confidence = (sum(p.confidence for p in pages) / len(pages)) if pages else 0.0
    low_confidence_pages = [p.page_number for p in pages if p.confidence < LOW_CONFIDENCE_THRESHOLD]
    return OcrExtraction(content=content, pages=pages, mean_confidence=mean_confidence, low_confidence_pages=low_confidence_pages)
