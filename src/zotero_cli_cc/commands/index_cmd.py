from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click

from zotero_cli_cc.config import (
    CONFIG_DIR,
    get_data_dir,
    load_config,
    load_embedding_config,
    load_pdf_config,
    resolve_library_id,
)
from zotero_cli_cc.core.rag import (
    build_metadata_chunk,
    chunk_text,
    compute_term_frequencies,
    convert_pdf_to_text,
    embed_texts,
    tokenize,
)
from zotero_cli_cc.core.rag_index import RagIndex
from zotero_cli_cc.core.reader import ZoteroReader


def _index_path(library_id: int) -> Path:
    return CONFIG_DIR / "index" / f"{library_id}.idx.sqlite"


@click.group("index")
def index_group() -> None:
    """Build and manage the full-library semantic search index."""


@index_group.command("build")
@click.option("--force", is_flag=True, help="Delete existing index and rebuild from scratch")
@click.option("--extractor", default=None, help="PDF extractor backend (pdfium, pymupdf, mineru)")
@click.pass_context
def index_build(ctx: click.Context, force: bool, extractor: str | None) -> None:
    """Build a full-library index for semantic search."""
    json_out = ctx.obj.get("json", False)
    if extractor is None:
        extractor = load_pdf_config().extractor

    cfg = load_config(profile=ctx.obj.get("profile"))
    data_dir = get_data_dir(cfg)
    db_path = data_dir / "zotero.sqlite"
    library_id = resolve_library_id(db_path, ctx.obj)
    reader = ZoteroReader(db_path, library_id=library_id)

    idx_path = _index_path(library_id)
    idx = RagIndex(idx_path)

    try:
        if force:
            idx.clear()

        already_indexed = idx.get_indexed_keys()

        all_item_ids = reader.get_all_item_ids()
        conn = reader._connect()
        all_items = reader._get_items_batch(conn, all_item_ids)

        to_index = [item for item in all_items if item.key not in already_indexed]

        if not to_index:
            if not json_out:
                click.echo(f"Index is up to date ({len(already_indexed)} item(s) indexed).")
            return

        t0 = time.monotonic()

        if not json_out:
            click.echo(f"  Indexing {len(to_index)} item(s) (skipping {len(already_indexed)} already indexed)...")

        all_chunks: list[tuple[str, str, str, int]] = []
        pdf_errors: list[tuple[str, str, Exception]] = []

        for i, item in enumerate(to_index, 1):
            if not json_out and i % 100 == 0:
                sys.stderr.write(f"\r{' ' * 60}\r    [prepare] [{i}/{len(to_index)}]")
                sys.stdout.flush()

            authors = ", ".join(c.full_name for c in item.creators)
            meta_text = build_metadata_chunk(item.title, authors, item.abstract, item.tags)
            meta_tokens = len(tokenize(meta_text))
            all_chunks.append((item.key, "metadata", meta_text, meta_tokens))

            att = reader.get_pdf_attachment(item.key)
            if att is not None and att.path is not None and att.path.exists():
                try:
                    pdf_text = convert_pdf_to_text(att.path, extractor_name=extractor)
                    for chunk_content in chunk_text(pdf_text, item.title):
                        chunk_tokens = len(tokenize(chunk_content))
                        all_chunks.append((item.key, "pdf", chunk_content, chunk_tokens))
                except Exception as e:
                    pdf_errors.append((item.key, att.path.name, e))

        if not json_out:
            sys.stderr.write(f"\r{' ' * 60}\r")
            sys.stdout.flush()
            click.echo(f"  Writing {len(all_chunks)} chunk(s)...")

        all_chunk_ids: list[int] = []
        all_chunk_texts: list[str] = []

        for i, (key, chunk_type, content, doc_len) in enumerate(all_chunks, 1):
            if not json_out and i % 500 == 0:
                sys.stderr.write(f"\r{' ' * 60}\r    [index] [{i}/{len(all_chunks)}]")
                sys.stdout.flush()

            chunk_id = idx.insert_chunk_no_commit(key, chunk_type, content, doc_len)
            tfs = compute_term_frequencies(tokenize(content))
            idx.insert_bm25_terms_no_commit(chunk_id, tfs)
            all_chunk_ids.append(chunk_id)
            all_chunk_texts.append(content)

        idx.commit()

        if not json_out:
            sys.stderr.write(f"\r{' ' * 60}\r")
            sys.stdout.flush()

        all_indexed_chunks = idx.get_all_chunks()
        total_docs = len(all_indexed_chunks)
        if total_docs > 0:
            total_len = sum(c.get("doc_len", 0) or len(tokenize(c["content"])) for c in all_indexed_chunks)
            avg_doc_len = total_len / total_docs
        else:
            avg_doc_len = 1.0
        idx.set_meta("total_docs", str(total_docs))
        idx.set_meta("avg_doc_len", str(avg_doc_len))
        idx.set_meta("chunk_count", str(total_docs))
        idx.set_meta("indexed_at", datetime.now(timezone.utc).isoformat())
        idx.set_meta("item_count", str(len(already_indexed) + len(to_index)))

        mode_label = "BM25"
        emb_cfg = load_embedding_config()
        if emb_cfg.is_configured and all_chunk_texts:
            if not json_out:
                click.echo("  Generating embeddings...")

            def emb_progress(done: int, total: int) -> None:
                if not json_out:
                    sys.stderr.write(f"\r{' ' * 60}\r    [embed] [{done}/{total}]")
                    sys.stdout.flush()

            try:
                vectors = embed_texts(all_chunk_texts, emb_cfg, emb_progress)
                if vectors:
                    idx.set_embeddings_bulk(all_chunk_ids, vectors)
                    mode_label = "BM25 + embeddings"
            except Exception as e:
                if not json_out:
                    click.echo(f"  [WARN] Embedding failed: {e}", err=True)
            if not json_out:
                sys.stderr.write(f"\r{' ' * 60}\r")
                sys.stdout.flush()

        if pdf_errors and not json_out:
            click.echo(f"\nWarning: {len(pdf_errors)} PDF extraction(s) failed:")
            for key, pdf_name, exc in pdf_errors:
                click.echo(f"  - {key} ({pdf_name}): {exc}")

        elapsed = time.monotonic() - t0
        if not json_out:
            total_items = len(already_indexed) + len(to_index)
            click.echo(
                f"Indexed {len(to_index)} new item(s) ({len(all_chunks)} chunks) "
                f"in {elapsed:.1f}s [{mode_label}]. Total: {total_items} item(s)."
            )
    finally:
        idx.close()
        reader.close()


@index_group.command("status")
@click.pass_context
def index_status(ctx: click.Context) -> None:
    """Show the status of the full-library index."""
    import json as json_mod

    from zotero_cli_cc.formatter import envelope_ok

    json_out = ctx.obj.get("json", False)
    cfg = load_config(profile=ctx.obj.get("profile"))
    data_dir = get_data_dir(cfg)
    db_path = data_dir / "zotero.sqlite"
    library_id = resolve_library_id(db_path, ctx.obj)

    idx_path = _index_path(library_id)
    if not idx_path.exists():
        if json_out:
            click.echo(
                json_mod.dumps(
                    envelope_ok({"exists": False, "hint": "Run 'zot index build' to create the index"}),
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            click.echo("No index found. Run 'zot index build' to create one.")
        return

    idx = RagIndex(idx_path)
    try:
        item_count = idx.get_meta("item_count") or str(len(idx.get_indexed_keys()))
        chunk_count = idx.get_meta("chunk_count") or "0"
        indexed_at = idx.get_meta("indexed_at") or "unknown"
        row = idx._conn.execute("SELECT 1 FROM chunks WHERE embedding IS NOT NULL LIMIT 1").fetchone()
        has_embeddings = row is not None

        data = {
            "exists": True,
            "item_count": int(item_count),
            "chunk_count": int(chunk_count),
            "indexed_at": indexed_at,
            "has_embeddings": has_embeddings,
            "index_path": str(idx_path),
        }

        if json_out:
            click.echo(json_mod.dumps(envelope_ok(data), indent=2, ensure_ascii=False))
        else:
            click.echo(f"Index: {idx_path}")
            click.echo(f"Items: {item_count}")
            click.echo(f"Chunks: {chunk_count}")
            click.echo(f"Embeddings: {'yes' if has_embeddings else 'no'}")
            click.echo(f"Last indexed: {indexed_at}")
    finally:
        idx.close()
