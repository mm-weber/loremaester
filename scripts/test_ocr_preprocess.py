"""Tests for ocr_preprocess.py"""
import sys

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from ocr_preprocess import (
    ocr_page, PageOcrResult, pdf_to_images, build_chunks, build_metadata,
    ingest_to_r2r, OcrReport, format_report, run_pipeline, main,
)


class TestOcrPage:
    @patch("ocr_preprocess.pytesseract.image_to_data", create=True)
    @patch("ocr_preprocess.pytesseract.image_to_string", create=True)
    def test_ocr_page_tesseract_returns_page_result(
        self, mock_image_to_string, mock_image_to_data
    ):
        mock_image_to_string.return_value = "Hello world"
        mock_image_to_data.return_value = pd.DataFrame({"conf": [92.0, -1]})
        image = MagicMock()

        result = ocr_page(image, page_number=1, engine="tesseract")

        assert result == PageOcrResult(page_number=1, text="Hello world", confidence=0.92)

    @patch("ocr_preprocess.pytesseract.image_to_data", create=True)
    @patch("ocr_preprocess.pytesseract.image_to_string", create=True)
    def test_ocr_page_surya_returns_page_result(
        self, mock_image_to_string, mock_image_to_data
    ):
        # Mock surya module
        mock_surya = MagicMock()
        mock_line = MagicMock()
        mock_line.text = "Dragon stats"
        mock_line.confidence = 0.85
        mock_result = MagicMock()
        mock_result.text_lines = [mock_line]
        mock_surya.run_recognition.return_value = [mock_result]

        image = MagicMock()

        with patch("ocr_preprocess.surya_ocr", mock_surya):
            result = ocr_page(image, page_number=3, engine="surya")

        assert result == PageOcrResult(page_number=3, text="Dragon stats", confidence=0.85)

    def test_ocr_page_invalid_engine_raises(self):
        image = MagicMock()
        with pytest.raises(ValueError, match="invalid"):
            ocr_page(image, page_number=1, engine="invalid")


class TestPdfToImages:
    @patch("ocr_preprocess.convert_from_path", create=True)
    def test_pdf_to_images_calls_convert_from_path(self, mock_convert):
        mock_images = [MagicMock(), MagicMock()]
        mock_convert.return_value = mock_images

        result = pdf_to_images("/path/to/doc.pdf")

        assert result == mock_images
        mock_convert.assert_called_once_with("/path/to/doc.pdf")

    @patch("ocr_preprocess.convert_from_path", create=True)
    def test_pdf_to_images_with_page_range(self, mock_convert):
        mock_convert.return_value = [MagicMock()]

        pdf_to_images("/path/to/doc.pdf", page_range="3-5")

        mock_convert.assert_called_once_with("/path/to/doc.pdf", first_page=3, last_page=5)


class TestBuildChunks:
    def test_build_chunks_preserves_page_boundaries(self):
        pages = [
            PageOcrResult(1, "aaa", 0.9),
            PageOcrResult(2, "bbb", 0.9),
        ]
        result = build_chunks(pages)
        assert result == ["[Page 1]\naaa", "[Page 2]\nbbb"]


class TestBuildMetadata:
    def test_build_metadata_full(self):
        result = build_metadata("Monster Manual", "Ch 1", "1-320")
        assert result == {"book_title": "Monster Manual", "chapter": "Ch 1", "page_range": "1-320"}

    def test_build_metadata_omits_none_fields(self):
        result = build_metadata("Monster Manual")
        assert result == {"book_title": "Monster Manual"}
        assert "chapter" not in result


class TestIngestToR2r:
    @patch("ocr_preprocess.R2RClient")
    def test_ingest_to_r2r_returns_ocr_report(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.results.document_id = "7a3f-abcd"
        mock_client.documents.create.return_value = mock_response

        chunks = ["[Page 1]\naaa", "[Page 2]\nbbb"]
        metadata = {"book_title": "Monster Manual"}
        page_results = [
            PageOcrResult(1, "aaa", 0.95),
            PageOcrResult(2, "bbb", 0.60),
        ]

        result = ingest_to_r2r(chunks, metadata, "Monster Manual", page_results)

        assert result.document_id == "7a3f-abcd"
        assert result.book_title == "Monster Manual"
        assert result.pages_processed == 2
        assert abs(result.average_confidence - 0.775) < 1e-9
        assert result.low_confidence_pages == [2]


class TestFormatReport:
    def test_format_report_output(self):
        report = OcrReport(
            book_title="Monster Manual",
            document_id="7a3f",
            pages_processed=320,
            average_confidence=0.87,
            low_confidence_pages=[12, 45],
        )
        output = format_report(report)
        assert "Ingested: Monster Manual" in output
        assert "Document ID: 7a3f" in output
        assert "Pages processed: 320" in output
        assert "Average confidence: 0.87" in output
        assert "Low-confidence pages: 12, 45" in output


class TestRunPipeline:
    @patch("ocr_preprocess.ingest_to_r2r")
    @patch("ocr_preprocess.ocr_page")
    @patch("ocr_preprocess.pdf_to_images")
    def test_run_pipeline_end_to_end(self, mock_pdf, mock_ocr, mock_ingest):
        mock_pdf.return_value = [MagicMock(), MagicMock()]
        mock_ocr.side_effect = [
            PageOcrResult(1, "aaa", 0.9),
            PageOcrResult(2, "bbb", 0.8),
        ]
        mock_ingest.return_value = OcrReport(
            book_title="Monster Manual",
            document_id="doc-123",
            pages_processed=2,
            average_confidence=0.85,
            low_confidence_pages=[],
        )

        result = run_pipeline("/path.pdf", "Monster Manual", engine="tesseract")

        assert result.document_id == "doc-123"
        assert result.pages_processed == 2


class TestCLI:
    @patch("ocr_preprocess.run_pipeline")
    def test_cli_main_calls_pipeline(self, mock_pipeline, capsys, monkeypatch):
        mock_pipeline.return_value = OcrReport(
            book_title="Monster Manual",
            document_id="abc-123",
            pages_processed=10,
            average_confidence=0.9,
            low_confidence_pages=[],
        )
        monkeypatch.setattr(sys, "argv", [
            "ocr_preprocess.py", "/path.pdf", "--book-title", "Monster Manual",
        ])

        main()

        output = capsys.readouterr().out
        assert "Ingested: Monster Manual" in output

    def test_cli_missing_book_title_exits(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["ocr_preprocess.py", "/path.pdf"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2
