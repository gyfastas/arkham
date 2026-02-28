---
name: feishu-sheets
description: Read and write Feishu spreadsheets (电子表格). Use when creating, reading, or writing to Feishu sheets/spreadsheets — NOT Bitable. Activate on keywords like "表格", "spreadsheet", "sheet", "电子表格", "飞书表格".
---

# Feishu Sheets

Feishu spreadsheets (sheets) are different from Bitable (多维表格):
- **Sheets** = Excel-like grid, use this skill
- **Bitable** = database/Airtable-like, use feishu_bitable_* tools

All sheet operations use `feishu_api.py` from `feishu-extra` skill.

```bash
FAPI="python3 /Users/bytedance/.openclaw/workspace/skills/feishu-extra/feishu_api.py"
```

---

## Workflow: Create & Write

```bash
# 1. Create spreadsheet in a folder
$FAPI sheets-create "实验结果" "PxPbfaCeclA7ObdwF3hcSEypnlf"
# → returns token, url

# 2. Get sheet tab ID
$FAPI sheets-meta "<spreadsheet_token>"
# → returns sheets[].id (e.g., "eed051")

# 3. Write header row
$FAPI sheets-write "<token>" "eed051!A1:D1" '[["Model","Params","Score","Date"]]'

# 4. Append data rows
$FAPI sheets-write "<token>" "eed051!A2:D4" '[["Qwen2-VL","7B",85.2,"2026-02"],["InternVL-2.5","8B",88.1,"2026-01"]]'
```

---

## Workflow: Read Existing Sheet

```bash
# Get spreadsheet token from URL:
# https://xxx.larkoffice.com/sheets/<token>

# Check structure
$FAPI sheets-meta "<token>"

# Read range
$FAPI sheets-read "<token>" "<sheet_id>!A1:Z100"
```

---

## Range Format

`<sheet_id>!<start>:<end>`

Examples:
- `eed051!A1:C10` — rows 1–10, columns A–C
- `eed051!A:A` — entire column A
- `eed051!1:1` — entire row 1
- `eed051!A1` — single cell

Get `sheet_id` from `sheets-meta` → `sheets[].id`.

---

## Common Patterns

### Write a table from Python list
```python
import sys, json, subprocess
FAPI = "python3 /Users/bytedance/.openclaw/workspace/skills/feishu-extra/feishu_api.py"

rows = [["Model", "Score"], ["Qwen2-VL", 85.2], ["InternVL", 88.1]]
subprocess.run([sys.executable,
    "/Users/bytedance/.openclaw/workspace/skills/feishu-extra/feishu_api.py",
    "sheets-write", token, f"{sheet_id}!A1:B3", json.dumps(rows)])
```

### Append row without knowing last row
```bash
$FAPI sheets-append "<token>" "<sheet_id>!A:A" '[["new row col1","col2","col3"]]'
```

### Add a new tab
```bash
$FAPI sheets-add-sheet "<token>" "实验结果-2026Q2"
```

---

## Folder Tokens (常用)

| 文件夹 | token |
|--------|-------|
| 根目录 workspace | `Sd1wflp6MlrUeYd0GQoc92KGnpc` |
| 实验汇总 | `PxPbfaCeclA7ObdwF3hcSEypnlf` |
| 每日总结 | `XT1YfPWpplzPWOdqGztczOUUnNb` |
| 论文调研 | `KnxxfsEU8lJU0ndy3QNc5s0vnxb` |

---

## Differences vs Bitable

| 功能 | Sheets | Bitable |
|------|--------|---------|
| 工具 | `feishu_api.py sheets-*` | `feishu_bitable_*` tools |
| 适合场景 | 表格数据、公式、图表 | 结构化数据库、筛选、关联 |
| 读写方式 | 行列范围 | record ID |
| 支持公式 | ✅ | ❌ |
| 支持关联字段 | ❌ | ✅ |
