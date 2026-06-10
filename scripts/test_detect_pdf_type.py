"""Tests for detect_pdf_type.py"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from detect_pdf_type import (
    PdfReport,
    analyze_pdf,
    classify_pdf_pages,
    format_report,
    main,
)


def _mock_pdf(mock_pdfplumber, page_texts):
    """Create a mock pdfplumber PDF with pages returning given texts."""
    mock_pages = []
    for text in page_texts:
        page = MagicMock()
        page.extract_text.return_value = text
        mock_pages.append(page)
    mock_pdf = MagicMock()
    mock_pdf.pages = mock_pages
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdfplumber.open.return_value = mock_pdf


class TestClassify:
    def test_all_text_returns_text_native(self):
        assert classify_pdf_pages(100, 100) == "text-native"

    def test_no_text_returns_image_only(self):
        assert classify_pdf_pages(0, 320) == "image-only"

    def test_half_text_returns_mixed(self):
        assert classify_pdf_pages(200, 400) == "mixed"

    def test_exactly_90_pct_is_text_native(self):
        assert classify_pdf_pages(90, 100) == "text-native"

    def test_exactly_10_pct_is_image_only(self):
        assert classify_pdf_pages(10, 100) == "image-only"

    def test_single_page_with_text(self):
        assert classify_pdf_pages(1, 1) == "text-native"


class TestAnalyzePdf:
    @patch("detect_pdf_type.pdfplumber")
    def test_text_native_pdf(self, mock_pdfplumber):
        _mock_pdf(mock_pdfplumber, ["x" * 100] * 3)
        report = analyze_pdf("book.pdf")
        assert report == PdfReport("book.pdf", "text-native", 3, 3)

    @patch("detect_pdf_type.pdfplumber")
    def test_image_only_pdf_none_text(self, mock_pdfplumber):
        _mock_pdf(mock_pdfplumber, [None] * 5)
        report = analyze_pdf("scanned.pdf")
        assert report.classification == "image-only"
        assert report.text_pages == 0

    @patch("detect_pdf_type.pdfplumber")
    def test_mixed_pdf(self, mock_pdfplumber):
        _mock_pdf(mock_pdfplumber, ["x" * 100] * 5 + [""] * 5)
        report = analyze_pdf("mixed.pdf")
        assert report.classification == "mixed"
        assert report.text_pages == 5

    @patch("detect_pdf_type.pdfplumber")
    def test_short_text_counts_as_image(self, mock_pdfplumber):
        _mock_pdf(mock_pdfplumber, ["x" * 49])
        report = analyze_pdf("short.pdf")
        assert report.text_pages == 0


class TestFormatReport:
    def test_format_report(self):
        report = PdfReport("Monster_Manual.pdf", "image-only", 320, 0)
        output = format_report(report)
        assert "Monster_Manual.pdf" in output
        assert "image-only" in output
        assert "0 of 320 pages have extractable text" in output


class TestCLI:
    @patch("detect_pdf_type.analyze_pdf")
    def test_cli_single_file(self, mock_analyze, capsys):
        mock_analyze.return_value = PdfReport("book.pdf", "text-native", 10, 10)
        with (
            patch.object(sys, "argv", ["detect_pdf_type.py", "book.pdf"]),
            patch("detect_pdf_type.Path") as mock_path,
        ):
            mock_path_inst = MagicMock()
            mock_path.return_value = mock_path_inst
            mock_path_inst.is_dir.return_value = False
            main()
        output = capsys.readouterr().out
        assert "book.pdf" in output
        assert "text-native" in output

    @patch("detect_pdf_type.analyze_pdf")
    def test_cli_directory(self, mock_analyze, capsys):
        mock_analyze.side_effect = [
            PdfReport("a.pdf", "text-native", 10, 10),
            PdfReport("b.pdf", "image-only", 5, 0),
        ]
        with (
            patch.object(sys, "argv", ["detect_pdf_type.py", "/some/dir"]),
            patch("detect_pdf_type.Path") as mock_path,
        ):
            mock_path_inst = MagicMock()
            mock_path.return_value = mock_path_inst
            mock_path_inst.is_dir.return_value = True
            mock_path_inst.glob.return_value = [Path("a.pdf"), Path("b.pdf")]
            main()
        output = capsys.readouterr().out
        assert "a.pdf" in output
        assert "b.pdf" in output

    def test_cli_no_args_exits(self):
        with (
            patch.object(sys, "argv", ["detect_pdf_type.py"]),
            pytest.raises(SystemExit),
        ):
            main()
