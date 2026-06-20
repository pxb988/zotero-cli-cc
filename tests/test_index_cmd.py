from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from zotero_cli_cc.commands.index_cmd import index_group
from zotero_cli_cc.models import Creator, Item


def _make_item(key: str, title: str, abstract: str | None = "An abstract") -> Item:
    return Item(
        key=key,
        item_type="journalArticle",
        title=title,
        creators=[Creator("Alice", "Smith", "author")],
        abstract=abstract,
        date="2024",
        url=None,
        doi=None,
        tags=["tag1"],
        collections=[],
        date_added="2024-01-01",
        date_modified="2024-01-01",
    )


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)
    ctx.obj["json"] = True
    ctx.obj["profile"] = None


cli.add_command(index_group, "index")


class TestIndexBuild:
    def test_build_creates_index(self, tmp_path: Path) -> None:
        items = [_make_item("K1", "Paper One"), _make_item("K2", "Paper Two", abstract=None)]
        idx_path = tmp_path / "test.idx.sqlite"

        mock_reader = MagicMock()
        mock_reader.get_all_item_ids.return_value = [1, 2]
        mock_reader._connect.return_value = MagicMock()
        mock_reader._get_items_batch.return_value = items
        mock_reader.get_pdf_attachment.return_value = None
        mock_reader.close.return_value = None

        with (
            patch("zotero_cli_cc.commands.index_cmd.load_config"),
            patch("zotero_cli_cc.commands.index_cmd.get_data_dir", return_value=tmp_path),
            patch("zotero_cli_cc.commands.index_cmd.resolve_library_id", return_value=1),
            patch("zotero_cli_cc.commands.index_cmd.ZoteroReader", return_value=mock_reader),
            patch("zotero_cli_cc.commands.index_cmd._index_path", return_value=idx_path),
            patch("zotero_cli_cc.commands.index_cmd.load_embedding_config") as mock_emb,
        ):
            mock_emb.return_value.is_configured = False
            runner = CliRunner()
            result = runner.invoke(cli, ["index", "build"])
            assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"

        from zotero_cli_cc.core.rag_index import RagIndex

        idx = RagIndex(idx_path)
        assert idx.get_indexed_keys() == {"K1", "K2"}
        assert idx.get_meta("total_docs") is not None
        idx.close()

    def test_build_incremental_skips_indexed(self, tmp_path: Path) -> None:
        idx_path = tmp_path / "test.idx.sqlite"

        from zotero_cli_cc.core.rag_index import RagIndex

        idx = RagIndex(idx_path)
        idx.insert_chunk("K1", "metadata", "Title: Paper One", 5)
        idx.close()

        mock_reader = MagicMock()
        mock_reader.get_all_item_ids.return_value = [1, 2]
        mock_reader._connect.return_value = MagicMock()
        mock_reader._get_items_batch.return_value = [_make_item("K1", "Paper One"), _make_item("K2", "Paper Two")]
        mock_reader.get_pdf_attachment.return_value = None
        mock_reader.close.return_value = None

        with (
            patch("zotero_cli_cc.commands.index_cmd.load_config"),
            patch("zotero_cli_cc.commands.index_cmd.get_data_dir", return_value=tmp_path),
            patch("zotero_cli_cc.commands.index_cmd.resolve_library_id", return_value=1),
            patch("zotero_cli_cc.commands.index_cmd.ZoteroReader", return_value=mock_reader),
            patch("zotero_cli_cc.commands.index_cmd._index_path", return_value=idx_path),
            patch("zotero_cli_cc.commands.index_cmd.load_embedding_config") as mock_emb,
        ):
            mock_emb.return_value.is_configured = False
            runner = CliRunner()
            result = runner.invoke(cli, ["index", "build"])
            assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"

        idx = RagIndex(idx_path)
        assert "K1" in idx.get_indexed_keys()
        assert "K2" in idx.get_indexed_keys()
        idx.close()

    def test_build_force_rebuilds(self, tmp_path: Path) -> None:
        items = [_make_item("K1", "Paper One")]
        idx_path = tmp_path / "test.idx.sqlite"

        from zotero_cli_cc.core.rag_index import RagIndex

        idx = RagIndex(idx_path)
        idx.insert_chunk("OLD", "metadata", "stale data", 2)
        idx.close()

        mock_reader = MagicMock()
        mock_reader.get_all_item_ids.return_value = [1]
        mock_reader._connect.return_value = MagicMock()
        mock_reader._get_items_batch.return_value = items
        mock_reader.get_pdf_attachment.return_value = None
        mock_reader.close.return_value = None

        with (
            patch("zotero_cli_cc.commands.index_cmd.load_config"),
            patch("zotero_cli_cc.commands.index_cmd.get_data_dir", return_value=tmp_path),
            patch("zotero_cli_cc.commands.index_cmd.resolve_library_id", return_value=1),
            patch("zotero_cli_cc.commands.index_cmd.ZoteroReader", return_value=mock_reader),
            patch("zotero_cli_cc.commands.index_cmd._index_path", return_value=idx_path),
            patch("zotero_cli_cc.commands.index_cmd.load_embedding_config") as mock_emb,
        ):
            mock_emb.return_value.is_configured = False
            runner = CliRunner()
            result = runner.invoke(cli, ["index", "build", "--force"])
            assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"

        idx = RagIndex(idx_path)
        keys = idx.get_indexed_keys()
        assert "OLD" not in keys
        assert "K1" in keys
        idx.close()


class TestIndexStatus:
    def test_status_no_index(self, tmp_path: Path) -> None:
        with (
            patch("zotero_cli_cc.commands.index_cmd.load_config"),
            patch("zotero_cli_cc.commands.index_cmd.get_data_dir", return_value=tmp_path),
            patch("zotero_cli_cc.commands.index_cmd.resolve_library_id", return_value=1),
            patch("zotero_cli_cc.commands.index_cmd._index_path", return_value=tmp_path / "nonexistent.idx.sqlite"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["index", "status"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["data"]["exists"] is False

    def test_status_with_index_json(self, tmp_path: Path) -> None:
        idx_path = tmp_path / "test.idx.sqlite"
        from zotero_cli_cc.core.rag_index import RagIndex

        idx = RagIndex(idx_path)
        idx.insert_chunk("K1", "metadata", "Title: Paper One", 5)
        idx.set_meta("item_count", "1")
        idx.set_meta("chunk_count", "1")
        idx.set_meta("indexed_at", "2024-01-01T00:00:00+00:00")
        idx.close()

        with (
            patch("zotero_cli_cc.commands.index_cmd.load_config"),
            patch("zotero_cli_cc.commands.index_cmd.get_data_dir", return_value=tmp_path),
            patch("zotero_cli_cc.commands.index_cmd.resolve_library_id", return_value=1),
            patch("zotero_cli_cc.commands.index_cmd._index_path", return_value=idx_path),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["index", "status"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            assert data["data"]["exists"] is True
            assert data["data"]["item_count"] == 1
            assert data["data"]["has_embeddings"] is False
