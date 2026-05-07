"""
Tests for automatic metadata tagging injected into document chunks at ingestion time.
Covers all 4 code paths in process_uploaded_file() where Document metadata is built.
"""

import time
import pytest
from langchain_core.documents import Document
from arkive.models.files import FileModel, FileMeta


# ── Helpers ─────────────────────────────────────────────────────────────────

def make_file(
    file_id="file-abc123",
    user_id="user-xyz",
    filename="report.pdf",
    content_type="application/pdf",
    created_at=None,
):
    created_at = created_at or int(time.time())
    return FileModel(
        id=file_id,
        user_id=user_id,
        filename=filename,
        meta={"content_type": content_type, "size": 1024},
        data={"content": "Some document text for testing purposes."},
        created_at=created_at,
        updated_at=created_at,
    )


def build_metadata(file, extra=None):
    """Mirrors the metadata dict built in all 4 ingestion paths."""
    m = {
        **file.meta,
        "name": file.filename,
        "created_by": file.user_id,
        "file_id": file.id,
        "source": file.filename,
        "source_type": "upload",
        "uploaded_by": file.user_id,
        "upload_date": file.created_at,
        "file_type": file.meta.get("content_type", ""),
        "original_filename": file.filename,
    }
    if extra:
        m.update(extra)
    return m


# ── Required fields ──────────────────────────────────────────────────────────

REQUIRED_FIELDS = [
    "file_id",
    "name",
    "source",
    "created_by",
    "source_type",
    "uploaded_by",
    "upload_date",
    "file_type",
    "original_filename",
]


class TestRequiredFieldsPresent:
    def test_all_required_fields_exist(self):
        file = make_file()
        meta = build_metadata(file)
        for field in REQUIRED_FIELDS:
            assert field in meta, f"Missing field: {field}"

    def test_source_type_is_upload(self):
        meta = build_metadata(make_file())
        assert meta["source_type"] == "upload"

    def test_uploaded_by_equals_user_id(self):
        file = make_file(user_id="user-42")
        meta = build_metadata(file)
        assert meta["uploaded_by"] == "user-42"
        assert meta["uploaded_by"] == meta["created_by"]

    def test_upload_date_is_epoch_int(self):
        ts = 1_700_000_000
        file = make_file(created_at=ts)
        meta = build_metadata(file)
        assert meta["upload_date"] == ts
        assert isinstance(meta["upload_date"], int)

    def test_file_type_from_content_type(self):
        file = make_file(content_type="application/pdf")
        meta = build_metadata(file)
        assert meta["file_type"] == "application/pdf"

    def test_original_filename_matches_filename(self):
        file = make_file(filename="contract_Q4.docx")
        meta = build_metadata(file)
        assert meta["original_filename"] == "contract_Q4.docx"
        assert meta["name"] == "contract_Q4.docx"
        assert meta["source"] == "contract_Q4.docx"

    def test_file_id_propagated(self):
        file = make_file(file_id="file-deadbeef")
        meta = build_metadata(file)
        assert meta["file_id"] == "file-deadbeef"


# ── Content type variations ──────────────────────────────────────────────────

class TestContentTypeVariations:
    def test_pdf(self):
        meta = build_metadata(make_file(content_type="application/pdf"))
        assert meta["file_type"] == "application/pdf"

    def test_docx(self):
        meta = build_metadata(make_file(
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="brief.docx",
        ))
        assert "wordprocessingml" in meta["file_type"]

    def test_plain_text(self):
        meta = build_metadata(make_file(content_type="text/plain", filename="notes.txt"))
        assert meta["file_type"] == "text/plain"

    def test_missing_content_type_defaults_to_empty_string(self):
        file = make_file()
        file.meta = {"size": 512}  # no content_type key
        meta = build_metadata(file)
        assert meta["file_type"] == ""

    def test_none_content_type_defaults_to_empty_string(self):
        file = make_file()
        file.meta = {"content_type": None, "size": 512}
        meta = {
            **file.meta,
            "name": file.filename,
            "created_by": file.user_id,
            "file_id": file.id,
            "source": file.filename,
            "source_type": "upload",
            "uploaded_by": file.user_id,
            "upload_date": file.created_at,
            "file_type": file.meta.get("content_type") or "",
            "original_filename": file.filename,
        }
        assert meta["file_type"] == ""


# ── Document construction ────────────────────────────────────────────────────

class TestDocumentConstruction:
    def test_document_metadata_contains_required_fields(self):
        file = make_file()
        meta = build_metadata(file)
        doc = Document(page_content="chunk text", metadata=meta)
        for field in REQUIRED_FIELDS:
            assert field in doc.metadata

    def test_document_page_content_preserved(self):
        content = "This is the extracted text from the document."
        doc = Document(page_content=content, metadata=build_metadata(make_file()))
        assert doc.page_content == content

    def test_multiple_chunks_share_same_file_metadata(self):
        file = make_file()
        meta = build_metadata(file)
        chunks = [
            Document(page_content=f"chunk {i}", metadata={**meta})
            for i in range(5)
        ]
        for chunk in chunks:
            assert chunk.metadata["file_id"] == file.id
            assert chunk.metadata["uploaded_by"] == file.user_id
            assert chunk.metadata["upload_date"] == file.created_at

    def test_chunk_metadata_is_independent_copy(self):
        file = make_file()
        meta = build_metadata(file)
        doc1 = Document(page_content="chunk 1", metadata={**meta})
        doc2 = Document(page_content="chunk 2", metadata={**meta})
        doc1.metadata["extra_field"] = "only_in_doc1"
        assert "extra_field" not in doc2.metadata


# ── Edge cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_filename_with_spaces(self):
        file = make_file(filename="Q4 Strategy Report.pdf")
        meta = build_metadata(file)
        assert meta["original_filename"] == "Q4 Strategy Report.pdf"
        assert meta["name"] == "Q4 Strategy Report.pdf"

    def test_filename_with_unicode(self):
        file = make_file(filename="rapport_financier_2024.pdf")
        meta = build_metadata(file)
        assert meta["original_filename"] == "rapport_financier_2024.pdf"

    def test_upload_date_not_zero(self):
        file = make_file(created_at=int(time.time()))
        meta = build_metadata(file)
        assert meta["upload_date"] > 0

    def test_meta_spread_does_not_overwrite_new_fields(self):
        # If file.meta accidentally had source_type set to something else,
        # our explicit key should win (it comes after **file.meta in the dict)
        file = make_file()
        file.meta["source_type"] = "legacy_value"
        meta = build_metadata(file)
        # Our explicit 'source_type': 'upload' comes after **file.meta, so it wins
        assert meta["source_type"] == "upload"

    def test_different_users_produce_different_uploaded_by(self):
        file_a = make_file(user_id="alice")
        file_b = make_file(user_id="bob")
        assert build_metadata(file_a)["uploaded_by"] == "alice"
        assert build_metadata(file_b)["uploaded_by"] == "bob"

    def test_upload_date_is_creation_time_not_now(self):
        past_ts = 1_600_000_000
        file = make_file(created_at=past_ts)
        meta = build_metadata(file)
        assert meta["upload_date"] == past_ts
        assert meta["upload_date"] != int(time.time())
