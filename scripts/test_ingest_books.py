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


class TestProcessPdf:
    @patch("ingest_books.ingest_native")
    @patch("ingest_books.is_image_pdf", return_value=False)
    def test_already_exists_is_skipped(self, mock_is_image, mock_native):
        mock_native.side_effect = RuntimeError(
            "{'message': 'Document abc already exists. Submit a DELETE request ...', 'error_type': 'R2RException'}"
        )
        assert ingest_books.process_pdf(MagicMock(), Path("/b/Vol-I.pdf")) == "skipped"

    @patch("ingest_books.ingest_native")
    @patch("ingest_books.is_image_pdf", return_value=False)
    def test_other_error_is_failed(self, mock_is_image, mock_native):
        mock_native.side_effect = RuntimeError("connection refused")
        assert ingest_books.process_pdf(MagicMock(), Path("/b/Vol-I.pdf")) == "failed"

    @patch("ingest_books.ingest_native")
    @patch("ingest_books.is_image_pdf", return_value=False)
    def test_success_is_succeeded(self, mock_is_image, mock_native):
        assert ingest_books.process_pdf(MagicMock(), Path("/b/Vol-I.pdf")) == "succeeded"


class TestProcessPdfRouting:
    @patch("ingest_books.ingest_via_ocr")
    @patch("ingest_books.ingest_native")
    @patch("ingest_books.is_image_pdf", return_value=False)
    @patch("ingest_books.analyze_pdf")
    def test_text_native_routes_to_native(self, mock_analyze, mock_is_image, mock_native, mock_ocr):
        mock_analyze.return_value = MagicMock(classification="text-native")
        ingest_books.process_pdf(MagicMock(), Path("/b/Book.pdf"))
        mock_native.assert_called_once()
        mock_ocr.assert_not_called()

    @patch("ingest_books.ingest_via_ocr")
    @patch("ingest_books.ingest_native")
    @patch("ingest_books.is_image_pdf", return_value=False)
    @patch("ingest_books.analyze_pdf")
    def test_mixed_routes_to_ocr(self, mock_analyze, mock_is_image, mock_native, mock_ocr):
        mock_analyze.return_value = MagicMock(classification="mixed")
        ingest_books.process_pdf(MagicMock(), Path("/b/Book.pdf"))
        mock_ocr.assert_called_once()
        mock_native.assert_not_called()

    @patch("ingest_books.ingest_via_ocr")
    @patch("ingest_books.ingest_native")
    @patch("ingest_books.is_image_pdf", return_value=True)
    @patch("ingest_books.analyze_pdf")
    def test_image_only_routes_to_ocr(self, mock_analyze, mock_is_image, mock_native, mock_ocr):
        mock_analyze.return_value = MagicMock(classification="image-only")
        ingest_books.process_pdf(MagicMock(), Path("/b/Book.pdf"))
        mock_ocr.assert_called_once()
        mock_native.assert_not_called()
