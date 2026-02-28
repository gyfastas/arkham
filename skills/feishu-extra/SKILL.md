---
name: feishu-extra
description: Extended Feishu API operations not covered by built-in tools. Covers Drive search/upload/copy, Doc copy/import, and Sheets CRUD. Use when you need to search Drive, upload files, copy docs, or read/write spreadsheets.
---

# Feishu Extra API

Extends the built-in `feishu_drive`, `feishu_doc` tools with operations they don't support.
All calls go through `feishu_api.py` which auto-loads credentials from `~/.openclaw/openclaw.json`.

## Script Path

```
/Users/bytedance/.openclaw/workspace/skills/feishu-extra/feishu_api.py
```

Shorthand alias: `FAPI="python3 ~/.openclaw/workspace/skills/feishu-extra/feishu_api.py"`

---

## Drive: Search

```bash
python3 feishu_api.py drive-search "query"
```

Returns list of matching files with `name`, `type`, `token`, `url`, `owner`.
Searches across doc, docx, sheet, bitable, folder, file types.

---

## Drive: Upload File (< 20MB)

```bash
python3 feishu_api.py drive-upload /local/path/file.pdf <folder_token>
# Optional custom name:
python3 feishu_api.py drive-upload /local/path/file.pdf <folder_token> custom_name.pdf
```

Returns `file_token` of the uploaded file.

---

## Drive: Copy File

```bash
python3 feishu_api.py drive-copy <file_token> <type> <target_folder_token> [new_name]
# type: doc | docx | sheet | bitable | file
```

---

## Drive: Delete (move to trash)

```bash
python3 feishu_api.py drive-delete <file_token> <type>
```

Moves to trash (Feishu doesn't support permanent delete via API for bots).

---

## Doc: Copy

```bash
python3 feishu_api.py doc-copy <doc_token> <target_folder_token> [new_title]
```

Copies a docx to another folder. Good for duplicating templates.

---

## Sheets: Create

```bash
python3 feishu_api.py sheets-create "Sheet Title" <folder_token>
```

Returns `token`, `title`, `url` of the new spreadsheet.

---

## Sheets: Get Metadata

```bash
python3 feishu_api.py sheets-meta <spreadsheet_token>
```

Returns spreadsheet info + list of all sheet tabs with row/col counts.

---

## Sheets: Read Range

```bash
python3 feishu_api.py sheets-read <spreadsheet_token> "<SheetID>!A1:D10"
```

Range format: `SheetID!StartCell:EndCell`
- Get SheetID from `sheets-meta`
- Returns 2D array of values

Example:
```bash
python3 feishu_api.py sheets-read "HyTPsXXX" "0!A1:E5"
```

---

## Sheets: Write Range

```bash
python3 feishu_api.py sheets-write <spreadsheet_token> "<SheetID>!A1:C3" '[[row1], [row2]]'
```

Values is a JSON 2D array:
```bash
python3 feishu_api.py sheets-write "HyTPsXXX" "0!A1:B2" '[["Name","Score"],["Alice",95]]'
```

---

## Sheets: Append Rows

```bash
# Append after existing data (auto-finds last row)
python3 feishu_api.py sheets-append <spreadsheet_token> "<SheetID>!A:A" '[[row1],[row2]]'
```

---

## Sheets: Add New Sheet Tab

```bash
python3 feishu_api.py sheets-add-sheet <spreadsheet_token> "New Tab Name"
```

---

## Python API (import as module)

```python
import sys
sys.path.insert(0, str(Path.home() / ".openclaw/workspace/skills/feishu-extra"))
from feishu_api import (
    drive_search, drive_upload, drive_copy, drive_delete,
    doc_copy, sheets_create, sheets_meta, sheets_read,
    sheets_write, sheets_append, sheets_add_sheet
)

# Search
results = drive_search("VLM 调研")

# Create and write a sheet
sheet = sheets_create("实验结果汇总", "PxPbfaCeclA7ObdwF3hcSEypnlf")
meta = sheets_meta(sheet["token"])
sheet_id = meta["sheets"][0]["id"]
sheets_write(sheet["token"], f"{sheet_id}!A1:C1", [["Model", "Score", "Date"]])
```

---

## Known Limitations

- Upload max size: 20MB (use resumable upload API for larger files — not yet implemented)
- Delete: moves to trash only (permanent delete needs admin scope)
- Import doc: async job, polls up to 60 seconds
- Search: returns at most 20 results per call (no pagination yet)
