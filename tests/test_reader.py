import shutil
import sqlite3
from pathlib import Path

import pytest

from zotero_cli_cc.core.reader import ZoteroReader


@pytest.fixture
def reader(test_db_path: Path) -> ZoteroReader:
    return ZoteroReader(test_db_path)


class TestGetItem:
    def test_get_existing_item(self, reader: ZoteroReader):
        item = reader.get_item("ATTN001")
        assert item is not None
        assert item.title == "Attention Is All You Need"
        assert item.item_type == "journalArticle"
        assert item.doi == "10.5555/attention"
        assert item.date == "2017"
        assert len(item.creators) == 2
        assert item.creators[0].last_name == "Vaswani"

    def test_get_nonexistent_item(self, reader: ZoteroReader):
        item = reader.get_item("NONEXIST")
        assert item is None

    def test_get_item_tags(self, reader: ZoteroReader):
        item = reader.get_item("ATTN001")
        assert "transformer" in item.tags
        assert "attention" in item.tags

    def test_get_item_collections(self, reader: ZoteroReader):
        item = reader.get_item("ATTN001")
        assert "COLML01" in item.collections

    def test_get_book(self, reader: ZoteroReader):
        item = reader.get_item("DEEP003")
        assert item.item_type == "book"
        assert item.title == "Deep Learning"


class TestSearch:
    def test_search_by_title(self, reader: ZoteroReader):
        result = reader.search("attention")
        assert result.total > 0
        assert any(i.key == "ATTN001" for i in result.items)

    def test_search_by_creator(self, reader: ZoteroReader):
        result = reader.search("Vaswani")
        assert result.total > 0
        assert any(i.key == "ATTN001" for i in result.items)

    def test_search_by_tag(self, reader: ZoteroReader):
        result = reader.search("transformer")
        assert result.total >= 2

    def test_search_no_results(self, reader: ZoteroReader):
        result = reader.search("nonexistentquery12345")
        assert result.total == 0

    def test_search_with_collection_filter(self, reader: ZoteroReader):
        result = reader.search("", collection="Transformers")
        assert result.total > 0
        assert all(i.key == "ATTN001" for i in result.items)

    def test_search_with_collection_filter_by_key(self, reader: ZoteroReader):
        result = reader.search("", collection="COLML01")
        assert result.total > 0

    def test_search_with_limit(self, reader: ZoteroReader):
        result = reader.search("", limit=1)
        assert len(result.items) == 1


class TestNotes:
    def test_get_notes(self, reader: ZoteroReader):
        notes = reader.get_notes("ATTN001")
        assert len(notes) == 1
        assert "transformer architecture" in notes[0].content

    def test_get_notes_empty(self, reader: ZoteroReader):
        notes = reader.get_notes("DEEP003")
        assert len(notes) == 0


class TestCollections:
    def test_get_collections(self, reader: ZoteroReader):
        collections = reader.get_collections()
        assert len(collections) >= 1
        ml = next(c for c in collections if c.name == "Machine Learning")
        assert any(ch.name == "Transformers" for ch in ml.children)

    def test_get_collection_items(self, reader: ZoteroReader):
        items = reader.get_collection_items("COLML01")
        assert len(items) >= 2


class TestAttachments:
    def test_get_attachments(self, reader: ZoteroReader):
        attachments = reader.get_attachments("ATTN001")
        assert len(attachments) == 1
        assert attachments[0].content_type == "application/pdf"
        assert attachments[0].filename == "attention.pdf"

    def test_get_pdf_attachment(self, reader: ZoteroReader):
        att = reader.get_pdf_attachment("ATTN001")
        assert att is not None
        assert att.key == "ATCH005"

    def test_get_pdf_attachment_none(self, reader: ZoteroReader):
        att = reader.get_pdf_attachment("DEEP003")
        assert att is None

    def test_attachment_tags_populated(self, reader: ZoteroReader):
        atts = {a.key: a for a in reader.get_attachments("BILI011")}
        assert atts["ATCH012"].tags == ["skip-index"]
        assert atts["ATCH013"].tags == []

    def test_get_pdf_attachment_returns_first_without_skip(self, reader: ZoteroReader):
        # Without a skip filter, the first PDF wins — here the translated copy.
        att = reader.get_pdf_attachment("BILI011")
        assert att is not None
        assert att.key == "ATCH012"

    def test_get_pdf_attachment_skips_tagged(self, reader: ZoteroReader):
        att = reader.get_pdf_attachment("BILI011", skip_tags={"skip-index"})
        assert att is not None
        assert att.key == "ATCH013"

    def test_get_pdf_attachment_skip_unmatched_tag(self, reader: ZoteroReader):
        # A skip set that matches nothing leaves the first PDF in place.
        att = reader.get_pdf_attachment("BILI011", skip_tags={"other"})
        assert att is not None
        assert att.key == "ATCH012"


class TestGetPdfAttachmentByKey:
    def test_hit(self, reader: ZoteroReader):
        # The addressed PDF belongs to the parent -> returned.
        att = reader.get_pdf_attachment_by_key("ATCH005", parent_key="ATTN001")
        assert att is not None
        assert att.key == "ATCH005"
        assert att.filename == "attention.pdf"

    def test_addresses_appendix_on_multi_pdf_item(self, reader: ZoteroReader):
        # BILI011 carries two PDFs; addressing the non-first one works.
        att = reader.get_pdf_attachment_by_key("ATCH013", parent_key="BILI011")
        assert att is not None
        assert att.key == "ATCH013"

    def test_parent_mismatch_returns_none(self, reader: ZoteroReader):
        # ATCH005 is a real PDF, but it belongs to ATTN001, not BILI011.
        att = reader.get_pdf_attachment_by_key("ATCH005", parent_key="BILI011")
        assert att is None

    def test_missing_attachment_returns_none(self, reader: ZoteroReader):
        att = reader.get_pdf_attachment_by_key("NONEXIST", parent_key="ATTN001")
        assert att is None

    def test_non_pdf_attachment_returns_none(self, test_db_path: Path, tmp_path: Path):
        # Copy the shared fixture and attach a non-PDF (HTML snapshot) to DEEP003,
        # which otherwise has no attachments. The non-PDF must not be addressable.
        db_copy = tmp_path / "zotero.sqlite"
        shutil.copy(test_db_path, db_copy)
        conn = sqlite3.connect(db_copy)
        # itemTypeID 14 == attachment; DEEP003 is itemID 3; pick a free itemID.
        conn.execute(
            "INSERT INTO items (itemID, itemTypeID, libraryID, key) VALUES (?, 14, 1, ?)",
            (9001, "SNAP9001"),
        )
        conn.execute(
            "INSERT INTO itemAttachments (itemID, parentItemID, linkMode, contentType, path) "
            "VALUES (?, 3, 0, 'text/html', 'storage:snapshot.html')",
            (9001,),
        )
        conn.commit()
        conn.close()
        reader = ZoteroReader(db_copy)
        try:
            assert reader.get_pdf_attachment_by_key("SNAP9001", parent_key="DEEP003") is None
        finally:
            reader.close()


class TestContextManager:
    def test_context_manager(self, test_db_path: Path):
        with ZoteroReader(test_db_path) as reader:
            item = reader.get_item("ATTN001")
            assert item is not None
        # Connection should be closed after exiting context
        assert reader._conn is None


class TestSchemaVersion:
    def test_check_schema_version(self, reader: ZoteroReader):
        version = reader.get_schema_version()
        assert version is not None
        assert isinstance(version, int)


class TestExportCitation:
    def test_export_bibtex(self, reader: ZoteroReader):
        bib = reader.export_citation("ATTN001", fmt="bibtex")
        assert "@article" in bib
        assert "Attention" in bib
        assert "Vaswani" in bib

    def test_export_csl_json(self, reader: ZoteroReader):
        import json

        csl = reader.export_citation("ATTN001", fmt="csl-json")
        assert csl is not None
        data = json.loads(csl)
        assert data["type"] == "article-journal"
        assert data["title"] == "Attention Is All You Need"
        assert data["DOI"] == "10.5555/attention"
        assert any(a["family"] == "Vaswani" for a in data["author"])

    def test_export_ris(self, reader: ZoteroReader):
        ris = reader.export_citation("ATTN001", fmt="ris")
        assert ris is not None
        assert "TY  - JOUR" in ris
        assert "TI  - Attention Is All You Need" in ris
        assert "AU  - Vaswani," in ris
        assert "DO  - 10.5555/attention" in ris
        assert "ER  - " in ris

    def test_export_unsupported_format(self, reader: ZoteroReader):
        result = reader.export_citation("ATTN001", fmt="xml")
        assert result is None

    def test_export_nonexistent(self, reader: ZoteroReader):
        bib = reader.export_citation("NONEXIST", fmt="bibtex")
        assert bib is None


class TestRelatedItems:
    def test_explicit_relation(self, reader: ZoteroReader):
        related = reader.get_related_items("ATTN001")
        keys = [i.key for i in related]
        assert "BERT002" in keys

    def test_implicit_relation_shared_tags(self, reader: ZoteroReader):
        related = reader.get_related_items("ATTN001")
        keys = [i.key for i in related]
        assert "BERT002" in keys

    def test_no_relations(self, reader: ZoteroReader):
        related = reader.get_related_items("DEEP003")
        assert isinstance(related, list)


def test_get_all_item_ids(reader: ZoteroReader):
    """get_all_item_ids returns all non-excluded item IDs in the library."""
    ids = reader.get_all_item_ids()
    assert isinstance(ids, list)
    assert len(ids) > 0
    assert all(isinstance(i, int) for i in ids)


def test_get_all_item_ids_excludes_trash(reader: ZoteroReader):
    """Items in the trash (deletedItems) must not be indexed. TRSH007 has itemID=7."""
    ids = reader.get_all_item_ids()
    assert 7 not in ids
