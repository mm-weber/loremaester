"""Tests for extract_text.py — all kreuzberg calls are mocked (no tesseract needed)."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import extract_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_main(args, monkeypatch):
    """Run extract_text.main() with given CLI args, return exit code."""
    monkeypatch.setattr(sys, "argv", ["extract_text.py"] + args)
    return extract_text.main()


# ---------------------------------------------------------------------------
# FR-1 / FR-2 / FR-3: single file → stdout
# ---------------------------------------------------------------------------

def test_extract_single_file(monkeypatch, capsys, tmp_path):
    f = tmp_path / "photo.jpeg"
    f.write_bytes(b"\xff\xd8dummy")

    with patch("extract_text._do_extract", return_value="Hello World"):
        code = run_main([str(f)], monkeypatch)

    assert code == 0
    assert "Hello World" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# FR-9: multiple files → separator headers
# ---------------------------------------------------------------------------

def test_extract_multiple_files(monkeypatch, capsys, tmp_path):
    f1 = tmp_path / "a.jpeg"
    f2 = tmp_path / "b.png"
    f1.write_bytes(b"\xff\xd8dummy")
    f2.write_bytes(b"\x89PNGdummy")

    def fake_extract(filepath, engine="tesseract", language="eng"):
        return {"a.jpeg": "Text A", "b.png": "Text B"}[Path(filepath).name]

    with patch("extract_text._do_extract", side_effect=fake_extract):
        code = run_main([str(f1), str(f2)], monkeypatch)

    out = capsys.readouterr().out
    assert code == 0
    assert "--- a.jpeg ---" in out
    assert "--- b.png ---" in out
    assert "Text A" in out
    assert "Text B" in out


# ---------------------------------------------------------------------------
# FR-4: --output writes to file
# ---------------------------------------------------------------------------

def test_output_to_file(monkeypatch, capsys, tmp_path):
    src = tmp_path / "img.jpeg"
    src.write_bytes(b"\xff\xd8dummy")
    dst = tmp_path / "result.txt"

    with patch("extract_text._do_extract", return_value="Extracted"):
        code = run_main([str(src), "--output", str(dst)], monkeypatch)

    assert code == 0
    assert dst.read_text() == "Extracted\n"
    # Nothing should go to stdout when --output is used
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# FR-5: --ingest calls R2R
# ---------------------------------------------------------------------------

def test_ingest_calls_r2r(monkeypatch, tmp_path):
    src = tmp_path / "contract.jpeg"
    src.write_bytes(b"\xff\xd8dummy")

    mock_client = MagicMock()

    with patch("extract_text._do_extract", return_value="clause text"), \
         patch("extract_text._get_r2r_client", return_value=mock_client):
        code = run_main([str(src), "--ingest"], monkeypatch)

    assert code == 0
    mock_client.documents.create.assert_called_once()
    call_kwargs = mock_client.documents.create.call_args
    assert "clause text" in str(call_kwargs)


# ---------------------------------------------------------------------------
# FR-6: default title = filename stem title-cased
# ---------------------------------------------------------------------------

def test_title_default(monkeypatch, tmp_path):
    src = tmp_path / "my_report.jpeg"
    src.write_bytes(b"\xff\xd8dummy")

    mock_client = MagicMock()

    with patch("extract_text._do_extract", return_value="text"), \
         patch("extract_text._get_r2r_client", return_value=mock_client):
        run_main([str(src), "--ingest"], monkeypatch)

    call_kwargs = mock_client.documents.create.call_args
    # Title should be derived from filename
    assert "My Report" in str(call_kwargs) or "My_Report" in str(call_kwargs)


# ---------------------------------------------------------------------------
# FR-6: --title override
# ---------------------------------------------------------------------------

def test_title_override(monkeypatch, tmp_path):
    src = tmp_path / "img.jpeg"
    src.write_bytes(b"\xff\xd8dummy")

    mock_client = MagicMock()

    with patch("extract_text._do_extract", return_value="text"), \
         patch("extract_text._get_r2r_client", return_value=mock_client):
        run_main([str(src), "--ingest", "--title", "Custom Title"], monkeypatch)

    call_kwargs = mock_client.documents.create.call_args
    assert "Custom Title" in str(call_kwargs)


# ---------------------------------------------------------------------------
# FR-7: --engine passes correct config to kreuzberg
# ---------------------------------------------------------------------------

def test_engine_selection(monkeypatch, capsys, tmp_path):
    src = tmp_path / "img.jpeg"
    src.write_bytes(b"\xff\xd8dummy")

    with patch("extract_text._do_extract", return_value="text") as mock_extract:
        run_main([str(src), "--engine", "easyocr"], monkeypatch)

    mock_extract.assert_called_once()
    # _do_extract(filepath, engine, language) — called positionally
    assert mock_extract.call_args[0][1] == "easyocr"


# ---------------------------------------------------------------------------
# FR-8: --language passes correct config to kreuzberg
# ---------------------------------------------------------------------------

def test_language_selection(monkeypatch, capsys, tmp_path):
    src = tmp_path / "img.jpeg"
    src.write_bytes(b"\xff\xd8dummy")

    with patch("extract_text._do_extract", return_value="text") as mock_extract:
        run_main([str(src), "--language", "deu"], monkeypatch)

    mock_extract.assert_called_once()
    # _do_extract(filepath, engine, language) — called positionally
    assert mock_extract.call_args[0][2] == "deu"


# ---------------------------------------------------------------------------
# FR-10: missing file → exit code 1
# ---------------------------------------------------------------------------

def test_missing_file(monkeypatch, capsys):
    code = run_main(["/nonexistent/file.jpeg"], monkeypatch)
    assert code == 1
    assert "not found" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# FR-10: no args → exit code 2
# ---------------------------------------------------------------------------

def test_no_args(monkeypatch, capsys):
    code = run_main([], monkeypatch)
    assert code == 2


# ---------------------------------------------------------------------------
# kreuzberg not installed → graceful error
# ---------------------------------------------------------------------------

def test_kreuzberg_not_installed(monkeypatch, capsys, tmp_path):
    src = tmp_path / "img.jpeg"
    src.write_bytes(b"\xff\xd8dummy")

    with patch("extract_text._do_extract", side_effect=ImportError("No module named 'kreuzberg'")):
        code = run_main([str(src)], monkeypatch)

    assert code == 1
    err = capsys.readouterr().err
    assert "kreuzberg" in err.lower()
