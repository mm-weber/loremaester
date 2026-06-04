# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pytesseract",
#   "pdf2image",
#   "Pillow",
#   "pandas",
#   "r2r",
# ]
# ///
"""OCR preprocessing utilities for scanned PDF pages."""
from dataclasses import dataclass, field
import types

try:
    import pytesseract
except ModuleNotFoundError:
    pytesseract = types.ModuleType("pytesseract")

try:
    import surya.recognition as surya_ocr
except ModuleNotFoundError:
    surya_ocr = types.ModuleType("surya_ocr")

try:
    from pdf2image import convert_from_path
except ModuleNotFoundError:
    convert_from_path = None

try:
    from r2r import R2RClient
except ModuleNotFoundError:
    R2RClient = None

LOW_CONFIDENCE_THRESHOLD = 0.7


@dataclass
class OcrReport:
    book_title: str
    document_id: str
    pages_processed: int
    average_confidence: float
    low_confidence_pages: list[int] = field(default_factory=list)


@dataclass
class PageOcrResult:
    page_number: int
    text: str
    confidence: float


def ocr_page(image, page_number=1, engine="tesseract"):
    if engine == "surya":
        results = surya_ocr.run_recognition(image)
        result = results[0]
        lines = result.text_lines
        text = "\n".join(line.text for line in lines)
        confidence = sum(line.confidence for line in lines) / len(lines)
        return PageOcrResult(page_number=page_number, text=text, confidence=confidence)
    elif engine == "tesseract":
        text = pytesseract.image_to_string(image)
        df = pytesseract.image_to_data(image, output_type="data.frame")
        valid = df[df["conf"] != -1]["conf"]
        confidence = valid.mean() / 100.0
        return PageOcrResult(page_number=page_number, text=text, confidence=confidence)
    else:
        raise ValueError(f"Unsupported OCR engine: {engine}")


def parse_page_range(range_str):
    first, last = range_str.split("-")
    return int(first), int(last)


def pdf_to_images(pdf_path, page_range=None):
    kwargs = {}
    if page_range:
        first, last = parse_page_range(page_range)
        kwargs["first_page"] = first
        kwargs["last_page"] = last
    return convert_from_path(pdf_path, **kwargs)


def build_chunks(page_results):
    return [f"[Page {p.page_number}]\n{p.text}" for p in page_results]


def build_metadata(book_title, chapter=None, page_range=None):
    metadata = {"book_title": book_title}
    if chapter is not None:
        metadata["chapter"] = chapter
    if page_range is not None:
        metadata["page_range"] = page_range
    return metadata


def ingest_to_r2r(chunks, metadata, book_title, page_results):
    client = R2RClient()
    response = client.documents.create(chunks=chunks, metadata=metadata)
    document_id = response.results.document_id
    avg_confidence = sum(p.confidence for p in page_results) / len(page_results)
    low_confidence_pages = [p.page_number for p in page_results if p.confidence < LOW_CONFIDENCE_THRESHOLD]
    return OcrReport(
        book_title=book_title,
        document_id=document_id,
        pages_processed=len(page_results),
        average_confidence=avg_confidence,
        low_confidence_pages=low_confidence_pages,
    )


def format_report(report):
    lines = [
        f"Ingested: {report.book_title}",
        f"Document ID: {report.document_id}",
        f"Pages processed: {report.pages_processed}",
        f"Average confidence: {report.average_confidence}",
    ]
    if report.low_confidence_pages:
        pages_str = ", ".join(str(p) for p in report.low_confidence_pages)
        lines.append(f"Low-confidence pages: {pages_str}")
    return "\n".join(lines)


def run_pipeline(pdf_path, book_title, engine="tesseract", chapter=None, page_range=None):
    images = pdf_to_images(pdf_path, page_range=page_range)
    page_results = [
        ocr_page(img, page_number=i + 1, engine=engine)
        for i, img in enumerate(images)
    ]
    chunks = build_chunks(page_results)
    metadata = build_metadata(book_title, chapter=chapter, page_range=page_range)
    return ingest_to_r2r(chunks, metadata, book_title, page_results)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="OCR preprocess and ingest PDF to R2R")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--book-title", required=True, help="Title of the book")
    parser.add_argument("--chapter", default=None, help="Chapter name")
    parser.add_argument("--page-range", default=None, help="Page range (e.g. 3-5)")
    parser.add_argument("--engine", default="tesseract", help="OCR engine (tesseract or surya)")
    args = parser.parse_args()
    report = run_pipeline(
        args.pdf_path, args.book_title,
        engine=args.engine, chapter=args.chapter, page_range=args.page_range,
    )
    print(format_report(report))


if __name__ == "__main__":
    main()
