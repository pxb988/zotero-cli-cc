# Workspaces & RAG

Workspaces are local topic-based paper collections for organizing research. Each workspace stores item keys in a TOML file (`~/.config/zot/workspaces/<name>.toml`) — no Zotero API needed.

> **Workspace RAG vs full-library semantic search**: `zot workspace query` searches within a curated set of papers (chunk-level results). `zot search --semantic` searches the entire library (item-level results). Use workspaces for focused research on a topic; use `--semantic` for broad discovery across the whole library.

## Workspace Management

```bash
# Create
zot workspace new llm-safety --description "LLM alignment and safety papers"

# Add/remove items
zot workspace add llm-safety KEY1 KEY2 KEY3
zot workspace remove llm-safety KEY1

# List and inspect
zot workspace list
zot --json workspace list
zot workspace show llm-safety

# Delete
zot workspace delete llm-safety --yes
```

## Bulk Import

```bash
zot workspace import llm-safety --collection "Alignment"
zot workspace import llm-safety --tag "safety"
zot workspace import llm-safety --search "RLHF"
```

## Search Within Workspace

Metadata substring match (no index required):

```bash
zot workspace search "reward" --workspace llm-safety
zot --json workspace search "attention" --workspace llm-safety
```

## Export

```bash
zot workspace export llm-safety                       # Markdown (default)
zot workspace export llm-safety --format json         # JSON
zot workspace export llm-safety --format bibtex       # BibTeX
```

## RAG Index

```bash
zot workspace index llm-safety                          # Incremental index
zot workspace index llm-safety --force                  # Full rebuild (slow — confirm with user first)
zot workspace index llm-safety --skip-tag skip-index    # Skip PDFs carrying this tag (default: skip-index)
```

Attachments tagged `skip-index` are skipped by default. Use `--skip-tag` to
change which tag(s) are excluded — useful for keeping huge or irrelevant PDFs
out of the index. Tag a PDF `skip-index` in Zotero to exclude it.

**Important**: Never `--force` rebuild without user confirmation. Incremental indexing is usually sufficient.

## RAG Query

```bash
zot workspace query "reward hacking" --workspace llm-safety
zot workspace query "RLHF methods" --workspace llm-safety --top-k 10
zot --json workspace query "attention" --workspace llm-safety
```

### Retrieval Modes

```bash
--mode bm25       # Keyword only (always available, zero deps)
--mode semantic   # Embeddings only (requires ZOT_EMBEDDING_URL + ZOT_EMBEDDING_KEY)
--mode hybrid     # BM25 + semantic fusion (auto-selected if embeddings available)
```

## Chunk Format

RAG results return chunks structured as:

```json
{
  "rank": 1,
  "score": 0.0154,
  "item_key": "B6TZ6TQX",
  "source": "pdf",
  "content": "[Title > Section Heading] chunk text..."
}
```

## Reading More Context from Chunks

When a chunk is incomplete, drill into the source:

```bash
zot --json pdf --outline ITEMKEY            # Get section headings + secid
zot --json pdf --section SECID ITEMKEY      # Extract full section
```

## Configuration

BM25 is always available with zero additional dependencies.

Semantic/hybrid search requires an embedding provider. Configure via `config.toml` (recommended) or environment variables:

### config.toml (`~/.config/zot/config.toml`)

```toml
[embedding]
provider = "zhipu"                              # jina | aliyun | zhipu
api_key = "your-api-key"
model = "embedding-3"                           # provider-specific model name
url = "https://open.bigmodel.cn/api/paas/v4"    # optional; defaults per provider
```

Provider defaults:

| Provider | Default URL | Default Model |
|----------|-------------|---------------|
| `jina` | `https://api.jina.ai/v1/embeddings` | `jina-embeddings-v3` |
| `aliyun` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `text-embedding-v3` |
| `zhipu` | `https://open.bigmodel.cn/api/paas/v4` | `embedding-3-pro` |

### Environment variables (override config.toml)

```bash
export ZOT_EMBEDDING_PROVIDER=zhipu
export ZOT_EMBEDDING_URL=https://open.bigmodel.cn/api/paas/v4
export ZOT_EMBEDDING_KEY=your-api-key
export ZOT_EMBEDDING_MODEL=embedding-3
```

## Known Issues

- **`workspace show` 默认只显示前 50 条**：受 `--limit` 全局默认值约束。查看全部条目需传 `--limit 999` 或更大值。
- **`uv sync` / `pip install --upgrade` 会覆盖 zhipu provider patch**：如果 zhipu 支持尚未发布到 PyPI（当前 PyPI 最新 0.7.0，zhipu 在 0.11.0），从 PyPI 升级会丢失该功能。使用源码安装（`uv sync`）或等待新版发布。
