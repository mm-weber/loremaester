from pathlib import Path
from unittest.mock import patch, MagicMock
import ingest_books


class TestIngestViaOcr:
    @patch("ingest_books.ocr_pdf")
    def test_ingest_via_ocr_ocrs_then_ingests_text(self, mock_ocr_pdf):
        mock_ocr_pdf.return_value = MagicMock(content="OCR TEXT")
        client = MagicMock()
        client.documents.create.return_value.results.document_id = "doc-1"
        ingest_books.ingest_via_ocr(client, Path("/books/Vol-III.pdf"), {"book_title": "Vol III"})
        mock_ocr_pdf.assert_called_once()                       # OCR done via ocr_extract
        _, kwargs = client.documents.create.call_args
        assert kwargs["file_path"].endswith("Vol-III.txt")     # temp .txt named after the PDF stem
        assert kwargs["metadata"] == {"book_title": "Vol III"}
