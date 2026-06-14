# PDF 提取

## 提取全文

```bash
zot pdf ABC123
```

从条目的 PDF 附件中提取文本。结果会缓存以加速后续访问。

## 提取指定页面

```bash
zot pdf ABC123 --pages 1-5     # 第 1 至 5 页
zot pdf ABC123 --pages 3       # 仅第 3 页
```

## 提取标注

```bash
zot pdf ABC123 --annotations
```

提取 PDF 中的高亮、批注和笔记，包含页码信息。

## 提取指定附件

默认 `zot pdf` 提取条目的**第一个** PDF。当一个条目挂有多个 PDF（正文 + 附录 / 补充材料）时，用 `--attachment` 按 attachment key 指定要提取的那一个：

```bash
zot --json attachment path ABC123              # 1. 列出每个 PDF 及其 attachment_key
zot pdf ABC123 --attachment DEF456             # 2. 提取指定的那个（如附录）
```

附件必须属于该条目——传入外来或非 PDF 的 key 会返回 `not_found`。`--attachment` 对所有提取模式生效（`--pages`、`--annotations`、`--references`、`--tables`、`--outline`、`--section`）。

## 缓存管理

PDF 文本在首次提取后会本地缓存：

```bash
zot config cache stats    # 查看缓存大小
zot config cache clear    # 清除所有缓存
```

## 在系统查看器中打开 PDF

```bash
zot open ABC123
```

使用默认应用程序打开 PDF（如果没有 PDF 则打开 URL）。
