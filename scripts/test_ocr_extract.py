"""Tests for ocr_extract.py"""
import pytest
from unittest.mock import patch, MagicMock
from ocr_extract import ocr_pdf, ocr_image, render_pages, PageOcrResult


class TestOcrPdf:
    @patch("ocr_extract.ocr_image")
    @patch("ocr_extract.render_pages")
    def test_ocr_pdf_ocrs_each_page_independently_in_order(self, mock_render, mock_ocr_image):
        mock_render.return_value = [MagicMock(), MagicMock(), MagicMock()]  # 3 pages
        mock_ocr_image.side_effect = [
            PageOcrResult(1, "alpha", 0.9),
            PageOcrResult(2, "bravo", 0.9),
            PageOcrResult(3, "charlie", 0.9),
        ]
        result = ocr_pdf("/x.pdf")
        assert result.content == "[Page 1]\nalpha\n\n[Page 2]\nbravo\n\n[Page 3]\ncharlie"
        assert mock_ocr_image.call_count == 3  # one OCR call PER PAGE, never the whole doc


class TestOcrImage:
    @patch("ocr_extract._HAS_TESSERACT", True)
    @patch("ocr_extract.pytesseract.image_to_data", create=True)
    @patch("ocr_extract.pytesseract.image_to_string", create=True)
    def test_ocr_image_tesseract_returns_text_and_confidence(self, mock_str, mock_data):
        mock_str.return_value = "Hello world"
        mock_data.return_value = {"conf": [92, -1, 88]}   # word confidences; -1 = no text
        image = MagicMock()
        result = ocr_image(image, page_number=1, engine="tesseract")
        assert result == PageOcrResult(page_number=1, text="Hello world", confidence=0.90)


class TestOcrPdfEasyocr:
    @patch("ocr_extract._HAS_EASYOCR", True)
    @patch("ocr_extract.easyocr.Reader", create=True)
    @patch("ocr_extract.render_pages")
    def test_ocr_pdf_easyocr_builds_one_reader_and_reads_each_page(self, mock_render, mock_reader_cls):
        mock_render.return_value = [MagicMock(), MagicMock()]  # 2 pages
        reader = MagicMock()
        reader.readtext.side_effect = [
            [(None, "page one", 0.9)],   # easyocr detail=1 result: (bbox, text, conf)
            [(None, "page two", 0.8)],
        ]
        mock_reader_cls.return_value = reader
        result = ocr_pdf("/x.pdf", engine="easyocr")
        assert mock_reader_cls.call_count == 1   # ONE reader for the whole doc
        assert reader.readtext.call_count == 2   # one readtext PER PAGE
        assert "page one" in result.content and "page two" in result.content


class TestOcrPdfAggregates:
    @patch("ocr_extract.ocr_image")
    @patch("ocr_extract.render_pages")
    def test_ocr_pdf_aggregates_confidence(self, mock_render, mock_ocr_image):
        mock_render.return_value = [MagicMock(), MagicMock()]
        mock_ocr_image.side_effect = [
            PageOcrResult(1, "a", 0.95),
            PageOcrResult(2, "b", 0.60),
        ]
        result = ocr_pdf("/x.pdf")
        assert abs(result.mean_confidence - 0.775) < 1e-9
        assert result.low_confidence_pages == [2]


class TestRenderPages:
    @patch("ocr_extract._HAS_PYPDFIUM2", True)
    @patch("ocr_extract.pypdfium2.PdfDocument", create=True)
    def test_render_pages_returns_one_pil_image_per_page(self, mock_pdfdoc):
        page0, page1 = MagicMock(), MagicMock()
        page0.render.return_value.to_pil.return_value = "img0"
        page1.render.return_value.to_pil.return_value = "img1"
        doc = MagicMock()
        doc.__len__.return_value = 2
        doc.__getitem__.side_effect = [page0, page1]
        mock_pdfdoc.return_value = doc
        result = render_pages("/x.pdf")
        assert result == ["img0", "img1"]
        mock_pdfdoc.assert_called_once_with("/x.pdf")


class TestMissingDependency:
    @patch("ocr_extract.pypdfium2.PdfDocument", create=True)
    @patch("ocr_extract._HAS_PYPDFIUM2", False)
    def test_render_pages_missing_pypdfium2_raises_actionable(self, mock_pdfdoc):
        doc = MagicMock(); doc.__len__.return_value = 0
        mock_pdfdoc.return_value = doc
        with pytest.raises(RuntimeError, match="pypdfium2"):
            render_pages("/x.pdf")


class TestEmptyText:
    @patch("ocr_extract.ocr_image")
    @patch("ocr_extract.render_pages")
    def test_ocr_pdf_all_empty_pages_raises_with_filename(self, mock_render, mock_ocr_image):
        mock_render.return_value = [MagicMock(), MagicMock()]
        mock_ocr_image.side_effect = [
            PageOcrResult(1, "", 0.0),
            PageOcrResult(2, "   ", 0.0),
        ]
        with pytest.raises(RuntimeError, match="Grunvyr-Vol-III"):
            ocr_pdf("/books/Grunvyr-Vol-III.pdf", engine="tesseract")
