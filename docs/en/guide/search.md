# Search & Browse

## How Search Works

`zot search` matches keywords across four layers:

1. **Titles & abstracts** — direct text match
2. **Author names** — first and last name matching
3. **Tags** — exact tag matching
4. **PDF fulltext index** — Zotero's built-in fulltext index

For full-library semantic ranking, use [`--semantic`](#full-library-semantic-search) (below). For deep content search over a curated subset of papers, use [workspace query](workspace.md).

## Full-Library Semantic Search

`zot search --semantic` ranks the entire library with BM25 plus optional embedding similarity, instead of the keyword matching above:

```bash
zot search "monetary policy transmission" --semantic
zot search "attention" --semantic --type book      # combine with filters
```

Results are item-level (ranked by relevance score), and standard filters like `--collection` / `--type` still apply.

`--semantic` requires a prebuilt index. Build it once, then refresh incrementally:

```bash
zot index build                 # build / update (incremental — only new items)
zot index build --force         # full rebuild from scratch
zot --json index status         # item count, chunk count, embedding availability
```

`zot index build` indexes every item (a metadata chunk for each, plus PDF text chunks for items with attachments) and **excludes items in the Zotero trash**. If you run `--semantic` before building the index, it exits with code `4` and a hint to run `zot index build`.

Embeddings are optional. Configure `[embedding]` in `config.toml` (or set `ZOT_EMBEDDING_URL` + `ZOT_EMBEDDING_KEY`) to enable hybrid retrieval (BM25 + cosine similarity with RRF fusion); without them, `--semantic` falls back to BM25-only ranking.

## Basic Search

```bash
zot search "transformer attention"
```

## Filter by Collection

```bash
zot search "BERT" --collection "NLP"
```

## Filter by Item Type

```bash
zot search "protein" --type journalArticle
```

Common types: `journalArticle`, `conferencePaper`, `preprint`, `book`, `bookSection`, `thesis`

## Sort Results

```bash
zot search "attention" --sort dateAdded --direction desc
zot search "attention" --sort title --direction asc
```

Sort fields: `dateAdded`, `dateModified`, `title`, `creator`

## List All Items

```bash
zot list --limit 20
zot list --collection "Machine Learning"
```

## Recently Added Items

```bash
zot recent                    # Last 7 days (default)
zot recent --days 30          # Last 30 days
zot recent --days 7 --modified  # Recently modified
```

## View Item Details

```bash
zot read ABC123
```

Shows metadata, abstract, and notes. Use `--detail full` for extra fields.

## Find Related Items

```bash
zot relate ABC123
```

Finds items sharing tags, collections, or explicit relations.

## Detail Levels

```bash
zot --detail minimal search "attention"   # Key, title, authors, year only
zot --detail standard read ABC123         # Default — includes abstract, tags, DOI
zot --detail full read ABC123             # All fields including extra metadata
```

## JSON Output

```bash
zot --json search "attention"
```

All commands support `--json` for machine-readable output.

## Library Statistics

```bash
zot stats
```

Shows total items, PDFs, notes, breakdown by type, collections, and top tags.
