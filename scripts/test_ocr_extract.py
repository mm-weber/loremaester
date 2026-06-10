"""Tests for ocr_extract.py"""

from unittest.mock import MagicMock, patch

import pytest
from ocr_extract import (
    PageOcrResult,
    extract_pdf,
    ocr_image,
    ocr_pdf,
    render_pages,
    resolve_engine,
)


class TestOcrPdf:
    @patch("ocr_extract.ocr_image")
    @patch("ocr_extract.render_pages")
    def test_ocr_pdf_ocrs_each_page_independently_in_order(
        self, mock_render, mock_ocr_image
    ):
        mock_render.return_value = [MagicMock(), MagicMock(), MagicMock()]  # 3 pages
        mock_ocr_image.side_effect = [
            PageOcrResult(1, "alpha", 0.9),
            PageOcrResult(2, "bravo", 0.9),
            PageOcrResult(3, "charlie", 0.9),
        ]
        result = ocr_pdf("/x.pdf")
        assert (
            result.content == "[Page 1]\nalpha\n\n[Page 2]\nbravo\n\n[Page 3]\ncharlie"
        )
        assert (
            mock_ocr_image.call_count == 3
        )  # one OCR call PER PAGE, never the whole doc


class TestOcrImage:
    @patch("ocr_extract._HAS_TESSERACT", True)
    @patch("ocr_extract.pytesseract.image_to_data", create=True)
    @patch("ocr_extract.pytesseract.image_to_string", create=True)
    def test_ocr_image_tesseract_returns_text_and_confidence(self, mock_str, mock_data):
        mock_str.return_value = "Hello world"
        mock_data.return_value = {
            "conf": [92, -1, 88]
        }  # word confidences; -1 = no text
        image = MagicMock()
        result = ocr_image(image, page_number=1, engine="tesseract")
        assert result == PageOcrResult(
            page_number=1, text="Hello world", confidence=0.90
        )


class TestOcrPdfEasyocr:
    @patch("ocr_extract._HAS_EASYOCR", True)
    @patch("ocr_extract.easyocr.Reader", create=True)
    @patch("ocr_extract.render_pages")
    def test_ocr_pdf_easyocr_builds_one_reader_and_reads_each_page(
        self, mock_render, mock_reader_cls
    ):
        mock_render.return_value = [MagicMock(), MagicMock()]  # 2 pages
        reader = MagicMock()
        reader.readtext.side_effect = [
            [(None, "page one", 0.9)],  # easyocr detail=1 result: (bbox, text, conf)
            [(None, "page two", 0.8)],
        ]
        mock_reader_cls.return_value = reader
        result = ocr_pdf("/x.pdf", engine="easyocr")
        assert mock_reader_cls.call_count == 1  # ONE reader for the whole doc
        assert reader.readtext.call_count == 2  # one readtext PER PAGE
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
        doc = MagicMock()
        doc.__len__.return_value = 0
        mock_pdfdoc.return_value = doc
        with pytest.raises(RuntimeError, match="pypdfium2"):
            render_pages("/x.pdf")


class TestEmptyText:
    @patch("ocr_extract.ocr_image")
    @patch("ocr_extract.render_pages")
    def test_ocr_pdf_all_empty_pages_raises_with_filename(
        self, mock_render, mock_ocr_image
    ):
        mock_render.return_value = [MagicMock(), MagicMock()]
        mock_ocr_image.side_effect = [
            PageOcrResult(1, "", 0.0),
            PageOcrResult(2, "   ", 0.0),
        ]
        with pytest.raises(RuntimeError, match="Grunvyr-Vol-III"):
            ocr_pdf("/books/Grunvyr-Vol-III.pdf", engine="tesseract")


class TestExtractPdfHybrid:
    @patch("ocr_extract.ocr_image")
    @patch("ocr_extract.render_pages")
    @patch("ocr_extract.pdfplumber")
    def test_uses_text_layer_and_ocrs_only_image_pages(
        self, mock_pdfplumber, mock_render, mock_ocr_image
    ):
        page0 = MagicMock()
        page0.extract_text.return_value = "real text"  # text page
        page0.images = []
        page1 = MagicMock()
        page1.extract_text.return_value = ""  # image page
        page1.images = []
        mock_pdf = MagicMock()
        mock_pdf.pages = [page0, page1]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        mock_render.return_value = ["img0", "img1"]
        mock_ocr_image.return_value = PageOcrResult(2, "ocr text", 0.9)

        result = extract_pdf("/x.pdf", engine="tesseract")

        assert result.content == "[Page 1]\nreal text\n\n[Page 2]\nocr text"
        assert mock_ocr_image.call_count == 1  # only the image page is OCR'd


class TestResolveEngine:
    @patch("ocr_extract._cuda_available", return_value=False)
    def test_easyocr_downgrades_to_tesseract_without_gpu(self, _cuda):
        assert resolve_engine("easyocr") == "tesseract"

    @patch("ocr_extract._cuda_available", return_value=True)
    def test_easyocr_kept_with_gpu(self, _cuda):
        assert resolve_engine("easyocr") == "easyocr"

    def test_tesseract_passes_through(self):
        assert resolve_engine("tesseract") == "tesseract"


class TestExtractPdfFigures:
    @patch("ocr_extract.ocr_image")
    @patch("ocr_extract.render_pages")
    @patch("ocr_extract.pdfplumber")
    def test_figure_region_ocrd_and_appended(
        self, mock_pdfplumber, mock_render, mock_ocr_image
    ):
        page = MagicMock()
        page.extract_text.return_value = "body text"
        page.width = 600
        page.height = 800
        page.images = [
            {"x0": 100, "top": 200, "x1": 300, "bottom": 400}
        ]  # a figure (not full-page)
        mock_pdf = MagicMock()
        mock_pdf.pages = [page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        rendered = MagicMock()
        rendered.width = 1200
        rendered.height = 1600
        mock_render.return_value = [rendered]
        mock_ocr_image.return_value = PageOcrResult(1, "FIGURE LABEL", 0.9)
        result = extract_pdf("/x.pdf", engine="tesseract")
        assert result.content == "[Page 1]\nbody text\nFIGURE LABEL"
        assert mock_ocr_image.call_count == 1

    @patch("ocr_extract.ocr_image")
    @patch("ocr_extract.render_pages")
    @patch("ocr_extract.pdfplumber")
    def test_figure_crop_maps_points_to_pixels(
        self, mock_pdfplumber, mock_render, mock_ocr_image
    ):
        page = MagicMock()
        page.extract_text.return_value = "body"
        page.width = 600
        page.height = 800
        page.images = [{"x0": 100, "top": 200, "x1": 300, "bottom": 400}]
        mock_pdf = MagicMock()
        mock_pdf.pages = [page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        rendered = MagicMock()
        rendered.width = 1200
        rendered.height = 1600  # scale x2
        mock_render.return_value = [rendered]
        mock_ocr_image.return_value = PageOcrResult(1, "X", 0.9)
        extract_pdf("/x.pdf", engine="tesseract")
        rendered.crop.assert_called_once_with(
            (200, 400, 600, 800)
        )  # bbox x (1200/600, 1600/800)

    @patch("ocr_extract.ocr_image")
    @patch("ocr_extract.render_pages")
    @patch("ocr_extract.pdfplumber")
    def test_full_page_image_skipped_when_text_layer(
        self, mock_pdfplumber, mock_render, mock_ocr_image
    ):
        page = MagicMock()
        page.extract_text.return_value = "body text"
        page.width = 600
        page.height = 800
        page.images = [{"x0": 0, "top": 0, "x1": 600, "bottom": 800}]  # full-page image
        mock_pdf = MagicMock()
        mock_pdf.pages = [page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf
        mock_render.return_value = [MagicMock(width=1200, height=1600)]
        mock_ocr_image.return_value = PageOcrResult(1, "SHOULD NOT APPEAR", 0.9)
        result = extract_pdf("/x.pdf", engine="tesseract")
        assert result.content == "[Page 1]\nbody text"
        assert mock_ocr_image.call_count == 0
