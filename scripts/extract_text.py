#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "kreuzberg",
#   "r2r",
# ]
# ///
"""extract_text.py — Extract text from images/documents using kreuzberg OCR.

Usage:
    python extract_text.py <file>...
    python extract_text.py --output result.txt <file>...
    python extract_text.py --ingest --title "Doc Name" <file>...
    python extract_text.py --engine paddleocr --language deu <file>...
"""

import argparse
import sys
from pathlib import Path

try:
    from kreuzberg import ExtractionConfig, OcrConfig, extract_file_sync
except ImportError:
    # Allow the module to load so tests can mock extract_file_sync.
    # Actual ImportError is raised at call time in _do_extract.
    extract_file_sync = None
    ExtractionConfig = None
    OcrConfig = None


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="extract_text.py",
        description="Extract text from images and documents using kreuzberg OCR.",
    )
    parser.add_argument("files", nargs="*", help="File(s) to extract text from")
    parser.add_argument("--output", "-o", help="Write extracted text to FILE instead of stdout")
    parser.add_argument("--ingest", action="store_true", help="Push extracted text into R2R")
    parser.add_argument("--title", help="Document title for R2R metadata (default: filename stem)")
    parser.add_argument("--engine", default="tesseract",
                        choices=["tesseract", "easyocr", "paddleocr"],
                        help="OCR backend (default: tesseract)")
    parser.add_argument("--language", default="eng", help="OCR language (default: eng)")
    return parser


def _get_r2r_client():
    from r2r import R2RClient
    return R2RClient()


def _do_extract(filepath, engine="tesseract", language="eng"):
    """Extract text from a single file. Returns content string or raises."""
    config = ExtractionConfig(ocr=OcrConfig(backend=engine, language=language))
    result = extract_file_sync(filepath, config=config)
    return result.content


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if not args.files:
        parser.print_usage(sys.stderr)
        return 2

    had_error = False
    results = []

    for filepath_str in args.files:
        filepath = Path(filepath_str)

        if not filepath.exists():
            print(f"Error: file not found: {filepath}", file=sys.stderr)
            had_error = True
            continue

        try:
            content = _do_extract(filepath, args.engine, args.language)
        except ImportError:
            print("Error: kreuzberg is not installed.", file=sys.stderr)
            print("Install it with: pip install kreuzberg", file=sys.stderr)
            had_error = True
            continue
        except Exception as e:
            print(f"Error extracting {filepath}: {e}", file=sys.stderr)
            had_error = True
            continue

        results.append((filepath.name, content))

        if args.ingest:
            title = args.title or filepath.stem.replace("_", " ").title()
            try:
                client = _get_r2r_client()
                client.documents.create(raw_text=content, metadata={"title": title})
            except Exception as e:
                print(f"Error ingesting {filepath.name} into R2R: {e}", file=sys.stderr)
                had_error = True

    # Output
    if results:
        multi = len(results) > 1
        lines = []
        for name, content in results:
            if multi:
                lines.append(f"--- {name} ---")
            lines.append(content)
            if multi:
                lines.append("")

        text = "\n".join(lines)
        if not text.endswith("\n"):
            text += "\n"

        if args.output:
            Path(args.output).write_text(text)
        else:
            sys.stdout.write(text)

    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
