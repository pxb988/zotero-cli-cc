# 搜索与浏览

## 搜索原理

`zot search` 在四个层面进行关键词匹配：

1. **标题与摘要** — 直接文本匹配
2. **作者姓名** — 姓和名匹配
3. **标签** — 精确标签匹配
4. **PDF 全文索引** — Zotero 内置的全文索引

如需对**全库**做语义排序，使用 `--semantic`（见下方「全库语义检索」一节）。如需在精选的少量论文子集上做深度内容检索，请使用 [工作区查询](workspace.md)。

## 全库语义检索

`zot search --semantic` 不再用上面的关键词匹配，而是用 BM25 加可选的向量相似度对整个文献库排序：

```bash
zot search "monetary policy transmission" --semantic
zot search "attention" --semantic --type book      # 可与过滤条件组合
```

结果为条目级别（按相关度分数排序），`--collection` / `--type` 等常规过滤条件仍然生效。

`--semantic` 需要预先构建索引。构建一次后即可增量刷新：

```bash
zot index build                 # 构建 / 更新（增量，仅处理新条目）
zot index build --force         # 从头全量重建
zot --json index status         # 条目数、chunk 数、是否启用向量
```

`zot index build` 会为每个条目建立元数据 chunk（有 PDF 附件的条目还会加正文 chunk），并**排除 Zotero 回收站中的条目**。若在构建索引前就运行 `--semantic`，命令会以退出码 `4` 退出并提示先运行 `zot index build`。

向量是可选的：在 `config.toml` 配置 `[embedding]`（或设置 `ZOT_EMBEDDING_URL` + `ZOT_EMBEDDING_KEY`）即可启用混合检索（BM25 + 余弦相似度，RRF 融合）；不配置时 `--semantic` 退化为纯 BM25 排序。

## 基本搜索

```bash
zot search "transformer attention"
```

## 按集合过滤

```bash
zot search "BERT" --collection "NLP"
```

## 按条目类型过滤

```bash
zot search "protein" --type journalArticle
```

常用类型：`journalArticle`、`conferencePaper`、`preprint`、`book`、`bookSection`、`thesis`

## 排序结果

```bash
zot search "attention" --sort dateAdded --direction desc
zot search "attention" --sort title --direction asc
```

排序字段：`dateAdded`、`dateModified`、`title`、`creator`

## 列出所有条目

```bash
zot list --limit 20
zot list --collection "Machine Learning"
```

## 最近添加的条目

```bash
zot recent                    # 最近 7 天（默认）
zot recent --days 30          # 最近 30 天
zot recent --days 7 --modified  # 最近修改的
```

## 查看条目详情

```bash
zot read ABC123
```

显示元数据、摘要和笔记。使用 `--detail full` 查看所有字段。

## 查找相关条目

```bash
zot relate ABC123
```

查找共享标签、集合或显式关联的条目。

## 详情级别

```bash
zot --detail minimal search "attention"   # 仅显示键、标题、作者、年份
zot --detail standard read ABC123         # 默认 — 包含摘要、标签、DOI
zot --detail full read ABC123             # 所有字段，包括额外元数据
```

## JSON 输出

```bash
zot --json search "attention"
```

所有命令都支持 `--json` 获取机器可读输出。

## 文献库统计

```bash
zot stats
```

显示总条目数、PDF 数、笔记数、按类型分类、集合信息和热门标签。
