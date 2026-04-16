#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["r2r"]
# ///
"""Bulk-ingest PDFs into R2R with sourcebook metadata."""

import sys
from pathlib import Path
from r2r import R2RClient

R2R_BASE = "http://localhost:7272"

def ingest_pdf(client, pdf_path, metadata):
    result = client.documents.create(file_path=str(pdf_path), metadata=metadata)
    doc_id = result.results.document_id
    print(f"  Ingested: {pdf_path.name} -> {doc_id}")
    return doc_id

def main():
    if len(sys.argv) < 2:
        print("Usage: python ingest_books.py <folder_of_pdfs>")
        sys.exit(1)

    pdf_dir = Path(sys.argv[1])
    client = R2RClient(R2R_BASE)

    pdfs = sorted(pdf_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}")
        sys.exit(1)

    print(f"Found {len(pdfs)} PDF(s) in {pdf_dir}\n")

    succeeded = []
    failed = []

    for pdf in pdfs:
        book_title = pdf.stem.replace("_", " ").replace("-", " ").title()
        metadata = {"book_title": book_title}

        print(f"[{book_title}]")
        try:
            ingest_pdf(client, pdf, metadata)
            succeeded.append(pdf.name)
        except Exception as e:
            print(f"  FAILED: {pdf.name} — {e}")
            failed.append(pdf.name)

    print(f"\nDone. {len(succeeded)} succeeded, {len(failed)} failed.")
    if failed:
        print("Failed files:")
        for name in failed:
            print(f"  - {name}")

if __name__ == "__main__":
    main()
