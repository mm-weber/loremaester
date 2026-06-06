"""Tests for ocr_extract.py"""
from unittest.mock import patch, MagicMock
from ocr_extract import ocr_pdf, ocr_image, PageOcrResult


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
    @patch("ocr_extract.pytesseract.image_to_data", create=True)
    @patch("ocr_extract.pytesseract.image_to_string", create=True)
    def test_ocr_image_tesseract_returns_text_and_confidence(self, mock_str, mock_data):
        mock_str.return_value = "Hello world"
        mock_data.return_value = {"conf": [92, -1, 88]}   # word confidences; -1 = no text
        image = MagicMock()
        result = ocr_image(image, page_number=1, engine="tesseract")
        assert result == PageOcrResult(page_number=1, text="Hello world", confidence=0.90)
