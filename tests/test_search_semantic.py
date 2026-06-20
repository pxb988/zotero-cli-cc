from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from zotero_cli_cc.commands.search import search_cmd
from zotero_cli_cc.core.rag import build_metadata_chunk, compute_term_frequencies, tokenize
from zotero_cli_cc.core.rag_index import RagIndex
from zotero_cli_cc.models import Creator, Item


def _make_item(key: str, title: str, abstract: str = "About monetary policy transmission") -> Item:
    return Item(
        key=key,
        item_type="journalArticle",
        title=title,
        creators=[Creator("Alice", "Smith", "author")],
        abstract=abstract,
        date="2024",
        url=None,
        doi=None,
        tags=["economics"],
        collections=[],
        date_added="2024-01-01",
        date_modified="2024-01-01",
    )


def _build_test_index(idx_path: Path) -> None:
    idx = RagIndex(idx_path)
    items_data = [
        ("K1", "Monetary Policy Transmission in China"),
        ("K2", "Machine Learning for Image Recognition"),
    ]
    for key, title in items_data:
        content = build_metadata_chunk(title, "Alice Smith", "About " + title.lower(), ["test"])
        tokens = tokenize(content)
        doc_len = len(tokens)
        chunk_id = idx.insert_chunk_no_commit(key, "metadata", content, doc_len)
        tfs = compute_term_frequencies(tokens)
        idx.insert_bm25_terms_no_commit(chunk_id, tfs)
    idx.commit()
    all_chunks = idx.get_all_chunks()
    total_docs = len(all_chunks)
    total_len = sum(c["doc_len"] for c in all_chunks)
    idx.set_meta("total_docs", str(total_docs))
    idx.set_meta("avg_doc_len", str(total_len / total_docs if total_docs else 1))
    idx.close()


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)
    ctx.obj["json"] = True
    ctx.obj["profile"] = None
    ctx.obj["limit"] = 50
    ctx.obj["detail"] = "standard"


cli.add_command(search_cmd, "search")


class TestSearchSemantic:
    def test_semantic_returns_scored_items(self, tmp_path: Path) -> None:
        idx_path = tmp_path / "1.idx.sqlite"
        _build_test_index(idx_path)

        mock_reader = MagicMock()
        mock_reader.get_item.side_effect = lambda k: (
            _make_item(k, "Monetary Policy Transmission in China")
            if k == "K1"
            else _make_item(k, "Machine Learning for Image Recognition")
        )
        mock_reader.close.return_value = None

        with (
            patch("zotero_cli_cc.commands.search.load_config"),
            patch("zotero_cli_cc.commands.search.get_data_dir", return_value=tmp_path),
            patch("zotero_cli_cc.commands.search.resolve_library_id", return_value=1),
            patch("zotero_cli_cc.commands.search.ZoteroReader", return_value=mock_reader),
            patch("zotero_cli_cc.commands.search._semantic_index_path", return_value=idx_path),
            patch("zotero_cli_cc.commands.search.load_embedding_config") as mock_emb,
        ):
            mock_emb.return_value.is_configured = False
            runner = CliRunner()
            result = runner.invoke(cli, ["search", "monetary policy", "--semantic"])
            assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
            data = json.loads(result.output)
            assert data["ok"] is True
            assert len(data["data"]) > 0
            assert "score" in data["data"][0]
            assert data["data"][0]["key"] == "K1"

    def test_semantic_no_index_exits_4(self, tmp_path: Path) -> None:
        mock_reader = MagicMock()
        mock_reader.close.return_value = None

        with (
            patch("zotero_cli_cc.commands.search.load_config"),
            patch("zotero_cli_cc.commands.search.get_data_dir", return_value=tmp_path),
            patch("zotero_cli_cc.commands.search.resolve_library_id", return_value=1),
            patch("zotero_cli_cc.commands.search.ZoteroReader", return_value=mock_reader),
            patch("zotero_cli_cc.commands.search._semantic_index_path", return_value=tmp_path / "nope.idx.sqlite"),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["search", "test", "--semantic"])
            assert result.exit_code == 4

    def test_semantic_with_type_filter(self, tmp_path: Path) -> None:
        idx_path = tmp_path / "1.idx.sqlite"
        _build_test_index(idx_path)

        item_k1 = _make_item("K1", "Monetary Policy")
        item_k1.item_type = "book"

        mock_reader = MagicMock()
        mock_reader.get_item.side_effect = lambda k: item_k1 if k == "K1" else _make_item("K2", "ML Paper")
        mock_reader.close.return_value = None

        with (
            patch("zotero_cli_cc.commands.search.load_config"),
            patch("zotero_cli_cc.commands.search.get_data_dir", return_value=tmp_path),
            patch("zotero_cli_cc.commands.search.resolve_library_id", return_value=1),
            patch("zotero_cli_cc.commands.search.ZoteroReader", return_value=mock_reader),
            patch("zotero_cli_cc.commands.search._semantic_index_path", return_value=idx_path),
            patch("zotero_cli_cc.commands.search.load_embedding_config") as mock_emb,
        ):
            mock_emb.return_value.is_configured = False
            runner = CliRunner()
            result = runner.invoke(cli, ["search", "monetary", "--semantic", "--type", "book"])
            assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
            data = json.loads(result.output)
            assert data["ok"] is True
            # Only K1 (book) should be returned, not K2 (journalArticle)
            keys = [d["key"] for d in data["data"]]
            assert "K1" in keys
            assert "K2" not in keys

    def test_non_semantic_unchanged(self, tmp_path: Path) -> None:
        """Non-semantic search should work exactly as before."""
        from zotero_cli_cc.models import SearchResult

        mock_reader = MagicMock()
        mock_reader.search.return_value = SearchResult(items=[_make_item("K1", "Test")], total=1, query="test")
        mock_reader.close.return_value = None

        with (
            patch("zotero_cli_cc.commands.search.load_config"),
            patch("zotero_cli_cc.commands.search.get_data_dir", return_value=tmp_path),
            patch("zotero_cli_cc.commands.search.resolve_library_id", return_value=1),
            patch("zotero_cli_cc.commands.search.ZoteroReader", return_value=mock_reader),
        ):
            runner = CliRunner()
            result = runner.invoke(cli, ["search", "test"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["ok"] is True
            mock_reader.search.assert_called_once()
