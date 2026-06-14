# PDF Extraction

## Extract Full Text

```bash
zot pdf ABC123
```

Extracts text from the item's PDF attachment. Results are cached for fast subsequent access.

## Extract Specific Pages

```bash
zot pdf ABC123 --pages 1-5     # Pages 1 through 5
zot pdf ABC123 --pages 3       # Page 3 only
```

## Extract Annotations

```bash
zot pdf ABC123 --annotations
```

Extracts highlights, comments, and notes from the PDF with page numbers.

## Extract a Specific Attachment

By default `zot pdf` extracts the item's **first** PDF. When an item carries more than one (article + appendix/supplementary), use `--attachment` to target a specific one by its attachment key:

```bash
zot --json attachment path ABC123              # 1. list each PDF with its attachment_key
zot pdf ABC123 --attachment DEF456             # 2. extract the one you want (e.g. appendix)
```

The attachment must belong to the item — a foreign or non-PDF key returns `not_found`. The flag applies to every extraction mode (`--pages`, `--annotations`, `--references`, `--tables`, `--outline`, `--section`).

## Cache Management

PDF text is cached locally after first extraction:

```bash
zot config cache stats    # View cache size
zot config cache clear    # Clear all cached text
```

## Open PDF in System Viewer

```bash
zot open ABC123
```

Opens the PDF (or URL if no PDF) in your default application.
