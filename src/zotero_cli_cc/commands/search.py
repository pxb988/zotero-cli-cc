from __future__ import annotations

import json as json_mod
from dataclasses import asdict
from pathlib import Path

import click

from zotero_cli_cc.config import CONFIG_DIR, get_data_dir, load_config, load_embedding_config, resolve_library_id
from zotero_cli_cc.core.reader import ZoteroReader
from zotero_cli_cc.exit_codes import emit_error
from zotero_cli_cc.formatter import envelope_ok, format_items, stream_items


def _semantic_index_path(library_id: int) -> Path:
    """Return the path to the semantic index for *library_id*."""
    return CONFIG_DIR / "index" / f"{library_id}.idx.sqlite"


def _semantic_search(
    query: str,
    idx_path: Path,
    reader: ZoteroReader,
    *,
    collection: str | None,
    item_type: str | None,
    limit: int,
    json_out: bool,
) -> str:
    """Run BM25 (+ optional embedding) search over the library index."""
    from zotero_cli_cc.core.rag import bm25_score_chunks, embed_texts, reciprocal_rank_fusion, semantic_score_chunks
    from zotero_cli_cc.core.rag_index import RagIndex

    idx = RagIndex(idx_path)
    try:
        # --- retrieval -------------------------------------------------
        bm25_results = bm25_score_chunks(idx, query)

        emb_cfg = load_embedding_config()
        has_embeddings = bool(idx.get_all_embeddings())
        if has_embeddings and emb_cfg.is_configured:
            vecs = embed_texts([query], emb_cfg)
            if vecs:
                sem_results = semantic_score_chunks(idx, vecs[0])
                merged = reciprocal_rank_fusion(bm25_results, sem_results)
            else:
                merged = bm25_results
        else:
            merged = bm25_results

        # --- aggregate to item level (max score per item_key) ----------
        item_scores: dict[str, float] = {}
        for _chunk_id, score, chunk in merged:
            key = chunk["item_key"]
            if key not in item_scores or score > item_scores[key]:
                item_scores[key] = score

        ranked_keys = sorted(item_scores, key=lambda k: item_scores[k], reverse=True)

        # --- optional post-filters -------------------------------------
        col_keys: set[str] | None = None
        if collection:
            col_result = reader.search("", collection=collection, limit=999999)
            col_keys = {item.key for item in col_result.items}

        items_out: list[dict] = []
        for key in ranked_keys:
            if col_keys is not None and key not in col_keys:
                continue
            item = reader.get_item(key)
            if item is None:
                continue
            if item_type and item.item_type != item_type:
                continue
            d = asdict(item)
            d["score"] = round(item_scores[key], 4)
            items_out.append(d)
            if len(items_out) >= limit:
                break

        # --- format output ---------------------------------------------
        if json_out:
            env = envelope_ok(items_out, meta={"count": len(items_out)})
            return json_mod.dumps(env, indent=2, ensure_ascii=False)

        # Rich table for TTY
        from io import StringIO

        from rich.console import Console
        from rich.table import Table

        buf = StringIO()
        console = Console(file=buf, force_terminal=False, width=120)
        if not items_out:
            console.print("No results found.")
            return buf.getvalue()
        table = Table(show_header=True, header_style="bold")
        table.add_column("Key", style="cyan", width=10)
        table.add_column("Score", width=8)
        table.add_column("Title", width=46)
        table.add_column("Authors", width=25)
        table.add_column("Year", width=6)
        for d in items_out:
            authors = ", ".join(
                c.get("first_name", "") + " " + c.get("last_name", "") for c in (d.get("creators") or [])[:3]
            )
            table.add_row(d["key"], f"{d['score']:.4f}", d["title"], authors.strip(), d.get("date") or "")
        console.print(table)
        return buf.getvalue()
    finally:
        idx.close()


@click.command("search")
@click.argument("query")
@click.option(
    "--collection",
    default=None,
    help="Filter by Zotero collection (folder) name. Use 'zot collection list' to see available names.",
)
@click.option("--type", "item_type", default=None, help="Filter by item type (e.g. journalArticle, book, preprint)")
@click.option(
    "--sort",
    default=None,
    type=click.Choice(["dateAdded", "dateModified", "title", "creator"]),
    help="Sort results by field",
)
@click.option(
    "--direction",
    default="desc",
    type=click.Choice(["asc", "desc"]),
    help="Sort direction (default: desc)",
)
@click.option("--limit", default=None, type=int, help="Limit results (overrides global --limit)")
@click.option("--stream", is_flag=True, help="Emit NDJSON (one item per line) for incremental processing")
@click.option("--semantic", is_flag=True, help="Use semantic search (BM25 + optional embedding) over the library index")
@click.pass_context
def search_cmd(
    ctx: click.Context,
    query: str,
    collection: str | None,
    item_type: str | None,
    sort: str | None,
    direction: str,
    limit: int | None,
    stream: bool,
    semantic: bool,
) -> None:
    """Search the Zotero library by title, author, tag, or full text.

    \b
    Examples:
      zot search "transformer attention"
      zot search "GAN" --limit 5
      zot --json search "single cell"

    \b
    Filter by Zotero collection (folder):
      zot collection list                        # show available collections
      zot search "BERT" --collection "NLP"       # search within "NLP" collection

    \b
    Semantic search (requires 'zot index build' first):
      zot search "monetary policy transmission" --semantic
    """
    cfg = load_config(profile=ctx.obj.get("profile"))
    data_dir = get_data_dir(cfg)
    db_path = data_dir / "zotero.sqlite"
    library_id = resolve_library_id(db_path, ctx.obj)
    reader = ZoteroReader(db_path, library_id=library_id)
    try:
        limit = limit if limit is not None else ctx.obj.get("limit", cfg.default_limit)
        json_out = ctx.obj.get("json", False)

        if semantic:
            idx_path = _semantic_index_path(library_id)
            if not idx_path.exists():
                emit_error(
                    "not_found",
                    f"Semantic index not found at {idx_path}. Run 'zot index build' first.",
                    output_json=json_out,
                )
            click.echo(
                _semantic_search(
                    query,
                    idx_path,
                    reader,
                    collection=collection,
                    item_type=item_type,
                    limit=limit,
                    json_out=json_out,
                )
            )
            return

        try:
            result = reader.search(
                query, collection=collection, item_type=item_type, sort=sort, direction=direction, limit=limit
            )
        except ValueError as e:
            emit_error("validation_error", str(e), output_json=json_out)
        detail = ctx.obj.get("detail", "standard")
        if stream:
            click.echo(stream_items(result.items, detail=detail))
            return
        if not result.items:
            if json_out:
                click.echo(format_items([], output_json=True))
            else:
                click.echo("No results found.", err=True)
            return
        click.echo(format_items(result.items, output_json=json_out, detail=detail))
    finally:
        reader.close()
