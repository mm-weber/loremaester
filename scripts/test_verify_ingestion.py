"""Tests for verify_ingestion.py"""
import sys
from unittest.mock import MagicMock, patch
import pytest
from verify_ingestion import (
    is_garbled, CheckResult, VerificationReport,
    check_document_exists, check_chunk_count, check_text_quality,
    check_search_coherence, format_verification_report, run_verification,
    main,
)


class TestIsGarbled:
    def test_clean_english_text_is_not_garbled(self):
        assert is_garbled("The beholder has ten eye stalks") is False

    def test_high_non_ascii_text_is_garbled(self):
        assert is_garbled("§∈∀∃∅∇∆ñöü©®™") is True

    def test_no_dictionary_words_is_garbled(self):
        assert is_garbled("xkcd qwzp fhjl mnbv") is True

    def test_empty_text_is_garbled(self):
        assert is_garbled("") is True


class TestVerificationReport:
    def test_overall_status_is_worst_check(self):
        report = VerificationReport(
            book_title="Test",
            document_id="abc",
            checks=[
                CheckResult("A", "PASS", "ok"),
                CheckResult("B", "WARN", "meh"),
                CheckResult("C", "PASS", "ok"),
            ],
        )
        assert report.overall_status == "WARN"


class TestCheckDocumentExists:
    def test_document_found_success_returns_pass(self):
        client = MagicMock()
        client.documents.retrieve.return_value.results.status = "success"
        result = check_document_exists(client, "7a3f")
        assert result == CheckResult("Document exists", "PASS", "status: success")

    def test_document_not_found_returns_fail(self):
        client = MagicMock()
        client.documents.retrieve.side_effect = Exception("Not found")
        result = check_document_exists(client, "7a3f")
        assert result.status == "FAIL"
        assert "not found" in result.message.lower()


class TestCheckChunkCount:
    def test_sufficient_chunks_pass_low_warn_zero_fail(self):
        # > 10 chunks → PASS
        client = MagicMock()
        client.documents.list_chunks.return_value.total_entries = 847
        result = check_chunk_count(client, "7a3f")
        assert result.status == "PASS"

        # 1-10 chunks → WARN
        client.documents.list_chunks.return_value.total_entries = 5
        result = check_chunk_count(client, "7a3f")
        assert result.status == "WARN"

        # 0 chunks → FAIL
        client.documents.list_chunks.return_value.total_entries = 0
        result = check_chunk_count(client, "7a3f")
        assert result.status == "FAIL"


class TestCheckTextQuality:
    def test_all_clean_chunks_returns_pass(self):
        client = MagicMock()
        chunks = [MagicMock(text="The dragon breathes fire") for _ in range(5)]
        client.documents.list_chunks.return_value.results = chunks
        result = check_text_quality(client, "7a3f")
        assert result.status == "PASS"

    def test_majority_garbled_returns_fail(self):
        client = MagicMock()
        garbled = [MagicMock(text="§∈∀∃∅∇∆ñöü©®™") for _ in range(6)]
        clean = [MagicMock(text="The dragon breathes fire") for _ in range(4)]
        client.documents.list_chunks.return_value.results = garbled + clean
        result = check_text_quality(client, "7a3f")
        assert result.status == "FAIL"


class TestCheckSearchCoherence:
    def test_relevant_results_pass_and_no_results_fail(self):
        # PASS case: 5 results with avg score 0.72
        client = MagicMock()
        results = []
        for _ in range(5):
            r = MagicMock()
            r.document_id = "7a3f"
            r.score = 0.72
            results.append(r)
        client.retrieval.search.return_value.chunk_search_results = results
        result = check_search_coherence(client, "7a3f", "Monster Manual")
        assert result.status == "PASS"

        # FAIL case: no results
        client.retrieval.search.return_value.chunk_search_results = []
        result = check_search_coherence(client, "7a3f", "Monster Manual")
        assert result.status == "FAIL"


class TestFormatReport:
    def test_format_verification_report_output(self):
        report = VerificationReport(
            book_title="Monster Manual",
            document_id="7a3f",
            checks=[
                CheckResult("Document exists", "PASS", "status: success"),
                CheckResult("Chunk count", "WARN", "only 5 chunks"),
            ],
        )
        output = format_verification_report(report)
        assert "Verification: Monster Manual (ID: 7a3f" in output
        assert "[PASS]" in output
        assert "[WARN]" in output
        assert "Overall: WARN" in output


class TestRunVerification:
    @patch("verify_ingestion.check_search_coherence")
    @patch("verify_ingestion.check_text_quality")
    @patch("verify_ingestion.check_chunk_count")
    @patch("verify_ingestion.check_document_exists")
    def test_pipeline_runs_all_checks(self, mock_exists, mock_chunks, mock_quality, mock_search):
        mock_exists.return_value = CheckResult("Document exists", "PASS", "ok")
        mock_chunks.return_value = CheckResult("Chunk count", "PASS", "ok")
        mock_quality.return_value = CheckResult("Text quality", "PASS", "ok")
        mock_search.return_value = CheckResult("Search coherence", "PASS", "ok")

        client = MagicMock()
        result = run_verification(client, "7a3f", "Monster Manual")

        assert isinstance(result, VerificationReport)
        assert len(result.checks) == 4
        assert result.overall_status == "PASS"


class TestCLI:
    @patch("verify_ingestion.run_verification")
    @patch("verify_ingestion.R2RClient")
    def test_cli_with_document_id(self, mock_client_cls, mock_run, capsys, monkeypatch):
        mock_run.return_value = VerificationReport(
            book_title="Monster Manual",
            document_id="7a3f",
            checks=[CheckResult("Document exists", "PASS", "ok")],
        )
        monkeypatch.setattr(sys, "argv", [
            "verify_ingestion.py",
            "--document-id", "7a3f",
            "--book-title", "Monster Manual",
        ])
        main()
        output = capsys.readouterr().out
        assert "Verification: Monster Manual" in output

    def test_cli_missing_args_exits(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["verify_ingestion.py"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2
