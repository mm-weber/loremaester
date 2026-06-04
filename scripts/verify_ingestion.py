# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "r2r",
# ]
# ///
"""Verification script for OCR ingestion quality."""
from dataclasses import dataclass, field

try:
    from r2r import R2RClient
except ModuleNotFoundError:
    R2RClient = None

GARBLED_NON_ASCII_THRESHOLD = 0.3
GARBLED_WARN_RATIO = 0.2
GARBLED_FAIL_RATIO = 0.5
SEARCH_PASS_THRESHOLD = 0.3
MIN_CHUNK_COUNT = 10

COMMON_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "has", "have", "had",
    "in", "on", "at", "to", "for", "of", "with", "and", "or", "not",
    "it", "this", "that", "from", "by", "as", "be", "but", "if", "so",
}


def is_garbled(text):
    if not text or not text.strip():
        return True
    non_ascii = sum(1 for c in text if ord(c) > 127)
    if len(text) > 0 and non_ascii / len(text) > GARBLED_NON_ASCII_THRESHOLD:
        return True
    words = text.lower().split()
    if not any(w in COMMON_WORDS for w in words):
        return True
    return False


@dataclass
class CheckResult:
    name: str
    status: str
    message: str


@dataclass
class VerificationReport:
    book_title: str
    document_id: str
    checks: list[CheckResult] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    document_info: object = None

    @property
    def overall_status(self) -> str:
        priority = {"FAIL": 2, "WARN": 1, "PASS": 0}
        if not self.checks:
            return "PASS"
        return max(self.checks, key=lambda c: priority.get(c.status, 0)).status


def check_document_exists(client, document_id):
    """Returns (CheckResult, ingestion_status_string, metadata_dict, doc_response)."""
    try:
        response = client.documents.retrieve(id=document_id)
        status = response.results.ingestion_status
        metadata = response.results.metadata or {}
        return CheckResult("Document exists", "PASS", f"status: {status}"), str(status), metadata, response.results
    except Exception as e:
        return CheckResult("Document exists", "FAIL", f"Not found: {e}"), None, None, None


def check_chunk_count(client, document_id):
    try:
        response = client.documents.list_chunks(id=document_id)
        count = response.total_entries
    except Exception as e:
        return CheckResult("Chunk count", "FAIL", f"Could not retrieve chunks: {e}")
    if count > MIN_CHUNK_COUNT:
        return CheckResult("Chunk count", "PASS", f"{count} chunks")
    elif count > 0:
        return CheckResult("Chunk count", "WARN", f"only {count} chunks (expected >{MIN_CHUNK_COUNT})")
    else:
        return CheckResult("Chunk count", "FAIL", "0 chunks found")


def check_text_quality(client, document_id):
    try:
        response = client.documents.list_chunks(id=document_id)
        chunks = response.results
    except Exception as e:
        return CheckResult("Text quality", "FAIL", f"Could not retrieve chunks: {e}")
    if not chunks:
        return CheckResult("Text quality", "FAIL", "no chunks to analyze")
    garbled_count = sum(1 for c in chunks if is_garbled(c.text))
    ratio = garbled_count / len(chunks)
    if ratio > GARBLED_FAIL_RATIO:
        return CheckResult("Text quality", "FAIL", f"{garbled_count}/{len(chunks)} chunks garbled ({ratio:.0%})")
    elif ratio > GARBLED_WARN_RATIO:
        return CheckResult("Text quality", "WARN", f"{garbled_count}/{len(chunks)} chunks garbled ({ratio:.0%})")
    else:
        return CheckResult("Text quality", "PASS", f"{len(chunks) - garbled_count}/{len(chunks)} chunks clean")


def check_search_coherence(client, document_id, book_title):
    response = client.retrieval.search(query=book_title)
    chunk_results = response.results.chunk_search_results or []
    results = [r for r in chunk_results if str(r.document_id) == document_id]
    if not results:
        return CheckResult("Search coherence", "FAIL", "no search results for this document")
    avg_score = sum(r.score for r in results) / len(results)
    if avg_score >= SEARCH_PASS_THRESHOLD:
        return CheckResult("Search coherence", "PASS", f"avg score {avg_score:.2f} across {len(results)} results")
    else:
        return CheckResult("Search coherence", "WARN", f"low avg score {avg_score:.2f} across {len(results)} results")


def format_verification_report(report, verbose=False):
    lines = [f"Verification: {report.book_title} (ID: {report.document_id})"]
    if verbose and report.document_info:
        doc = report.document_info
        doc_type = getattr(doc, "document_type", None) or (report.metadata or {}).get("document_type", "unknown")
        size_bytes = getattr(doc, "size_in_bytes", None)
        created = getattr(doc, "created_at", None)
        updated = getattr(doc, "updated_at", None)
        lines.append(f"  Document type: {doc_type}")
        if size_bytes:
            if size_bytes >= 1_048_576:
                lines.append(f"  Size: {size_bytes / 1_048_576:.1f} MB")
            else:
                lines.append(f"  Size: {size_bytes / 1024:.1f} KB")
        if created:
            lines.append(f"  Created: {created}")
        if updated:
            lines.append(f"  Updated: {updated}")
    lines.append("")
    for check in report.checks:
        lines.append(f"  [{check.status}] {check.name}: {check.message}")
    if verbose and report.overall_status == "WARN":
        in_progress = any("still in progress" in c.message for c in report.checks)
        if in_progress:
            lines.append("")
            lines.append("  Hint: ingestion is still running — re-run this check in 30-60 seconds")
    lines.append("")
    lines.append(f"Overall: {report.overall_status}")
    return "\n".join(lines)


def run_verification(client, document_id, book_title):
    report = VerificationReport(book_title=book_title, document_id=document_id)
    exists_result, ingestion_status, metadata, doc_info = check_document_exists(client, document_id)
    report.checks.append(exists_result)
    report.metadata = metadata or {}
    report.document_info = doc_info

    if exists_result.status == "FAIL":
        return report

    # Gate chunk-dependent checks on ingestion status
    if ingestion_status != "success":
        if ingestion_status == "failed":
            failure_reason = (metadata or {}).get("failure", "unknown reason")
            report.checks.append(CheckResult("Ingestion status", "FAIL", f"ingestion failed — {failure_reason}"))
        else:
            report.checks.append(CheckResult("Ingestion status", "WARN",
                                             f"ingestion still in progress ({ingestion_status}) — chunk checks skipped"))
        return report

    report.checks.append(check_chunk_count(client, document_id))
    report.checks.append(check_text_quality(client, document_id))
    report.checks.append(check_search_coherence(client, document_id, book_title))
    return report


def find_document_by_title(client, book_title):
    """Search documents list for a matching book_title in metadata. Returns (document_id, book_title) or (None, None)."""
    offset = 0
    limit = 100
    while True:
        response = client.documents.list(offset=offset, limit=limit)
        for doc in response.results:
            doc_title = doc.metadata.get("book_title", "") if doc.metadata else ""
            if doc_title.lower() == book_title.lower():
                return str(doc.id), doc_title
        if offset + limit >= response.total_entries:
            break
        offset += limit
    return None, None


def get_all_documents(client):
    """Return list of (document_id, book_title) for all documents."""
    docs = []
    offset = 0
    limit = 100
    while True:
        response = client.documents.list(offset=offset, limit=limit)
        for doc in response.results:
            title = (doc.metadata or {}).get("book_title", "") or doc.title or str(doc.id)
            docs.append((str(doc.id), title))
        if offset + limit >= response.total_entries:
            break
        offset += limit
    return docs


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Verify OCR ingestion quality")
    parser.add_argument("--document-id", default=None, help="Document ID to verify")
    parser.add_argument("--book-title", default=None, help="Title of the book")
    parser.add_argument("--all", action="store_true", help="Verify all ingested documents")
    parser.add_argument("--engine", default=None, help="R2R engine base URL")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed document info")
    args = parser.parse_args()

    if not args.document_id and not args.book_title and not args.all:
        parser.error("Provide --document-id, --book-title, or --all")

    client = R2RClient(args.engine) if args.engine else R2RClient()

    if args.all:
        docs = get_all_documents(client)
        if not docs:
            print("No documents found.")
            sys.exit(1)

        counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for doc_id, title in docs:
            report = run_verification(client, doc_id, title)
            print(format_verification_report(report, verbose=args.verbose))
            print()
            counts[report.overall_status] = counts.get(report.overall_status, 0) + 1

        total = len(docs)
        print(f"Summary: {total} documents — {counts['PASS']} passed, {counts['WARN']} warned, {counts['FAIL']} failed")
        sys.exit(0)

    document_id = args.document_id
    book_title = args.book_title

    if document_id and not book_title:
        # Look up book_title from document metadata
        try:
            response = client.documents.retrieve(id=document_id)
            book_title = (response.results.metadata or {}).get("book_title", "") or response.results.title or document_id
        except Exception:
            book_title = document_id

    if book_title and not document_id:
        # Look up document_id from book_title
        document_id, _ = find_document_by_title(client, book_title)
        if not document_id:
            print(f"No document found with book_title matching \"{book_title}\"")
            sys.exit(1)

    report = run_verification(client, document_id, book_title)
    print(format_verification_report(report, verbose=args.verbose))


if __name__ == "__main__":
    main()
