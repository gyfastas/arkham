#!/usr/bin/env python3
"""
Feishu Extra API Helper
Implements Drive search/upload, Doc copy/import, and Sheets operations
via direct Feishu REST API calls using bot credentials from openclaw.json.

Usage:
    python3 feishu_api.py <command> [args...]

Commands:
    token                              - Get tenant_access_token
    drive-search <query>               - Search files in Drive
    drive-upload <local_path> <folder_token> - Upload file to Drive folder
    drive-delete <file_token> <type>   - Move file to trash (then delete)
    drive-copy <file_token> <type> <folder_token> [name] - Copy file
    doc-copy <doc_token> <folder_token> [title]   - Copy a document
    sheets-read <spreadsheet_token> <range>       - Read sheet cell range
    sheets-write <spreadsheet_token> <range> <json_values> - Write cells
    sheets-create <title> <folder_token>          - Create spreadsheet
    sheets-meta <spreadsheet_token>               - Get sheet metadata
    sheets-add-sheet <spreadsheet_token> <title>  - Add a new sheet
"""

import json, sys, os, requests, mimetypes
from pathlib import Path

# ── Credentials ──────────────────────────────────────────────────────────────

def _load_credentials():
    cfg_path = Path.home() / ".openclaw" / "openclaw.json"
    with open(cfg_path) as f:
        d = json.load(f)
    feishu = d.get("channels", {}).get("feishu", {})
    domain = feishu.get("domain", "feishu")  # feishu or lark
    base = "https://open.feishu.cn" if domain == "feishu" else "https://open.larksuite.com"
    return feishu["appId"], feishu["appSecret"], base

APP_ID, APP_SECRET, BASE_URL = _load_credentials()

# ── Token ─────────────────────────────────────────────────────────────────────

_token_cache = {}

def get_tenant_token():
    if _token_cache.get("token") and _token_cache.get("expire", 0) > __import__("time").time() + 60:
        return _token_cache["token"]
    r = requests.post(f"{BASE_URL}/open-apis/auth/v3/tenant_access_token/internal", json={
        "app_id": APP_ID, "app_secret": APP_SECRET
    })
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Token error: {data}")
    _token_cache["token"] = data["tenant_access_token"]
    _token_cache["expire"] = __import__("time").time() + data.get("expire", 7200)
    return _token_cache["token"]

def _headers():
    return {"Authorization": f"Bearer {get_tenant_token()}", "Content-Type": "application/json"}

def _get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params)
    r.raise_for_status()
    return r.json()

def _post(path, body=None):
    r = requests.post(f"{BASE_URL}{path}", headers=_headers(), json=body or {})
    r.raise_for_status()
    return r.json()

def _patch(path, body=None):
    r = requests.patch(f"{BASE_URL}{path}", headers=_headers(), json=body or {})
    r.raise_for_status()
    return r.json()

def _delete(path):
    r = requests.delete(f"{BASE_URL}{path}", headers=_headers())
    r.raise_for_status()
    return r.json()

# ── Drive: Search ──────────────────────────────────────────────────────────────

def drive_search(query: str, page_size: int = 20):
    """Search files/folders in Drive by keyword."""
    r = _post("/open-apis/suite/docs-api/search/object", {
        "search_key": query,
        "count": page_size,
        "offset": 0,
        "docs_types": ["doc", "docx", "sheet", "bitable", "folder", "file"]
    })
    if r.get("code") != 0:
        raise RuntimeError(f"Search error: {r}")
    items = r.get("data", {}).get("docs_entities", [])
    return [{"name": x.get("title"), "type": x.get("docs_type"), "token": x.get("docs_token"),
             "url": x.get("url"), "owner": x.get("owner_id")} for x in items]

# ── Drive: Upload (small file, <20MB) ─────────────────────────────────────────

def drive_upload(local_path: str, folder_token: str, file_name: str = None):
    """Upload a local file to a Drive folder."""
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"File not found: {local_path}")
    file_name = file_name or local_path.name
    file_size = local_path.stat().st_size
    mime_type = mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"

    token = get_tenant_token()
    url = f"{BASE_URL}/open-apis/drive/v1/files/upload_all"
    with open(local_path, "rb") as f:
        r = requests.post(url, headers={"Authorization": f"Bearer {token}"}, data={
            "file_name": file_name,
            "parent_type": "explorer",
            "parent_node": folder_token,
            "size": str(file_size),
        }, files={"file": (file_name, f, mime_type)})
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Upload error: {data}")
    return data.get("data", {})

# ── Drive: Copy ───────────────────────────────────────────────────────────────

def drive_copy(file_token: str, file_type: str, folder_token: str, name: str = None):
    """Copy a file/doc to another folder."""
    body = {"type": file_type, "folder_token": folder_token}
    if name:
        body["name"] = name
    r = _post(f"/open-apis/drive/v1/files/{file_token}/copy", body)
    if r.get("code") != 0:
        raise RuntimeError(f"Copy error: {r}")
    return r.get("data", {}).get("file", {})

# ── Drive: Delete (trash first) ────────────────────────────────────────────────

def drive_delete(file_token: str, file_type: str):
    """Move file to trash (Feishu bot delete = move to recycle bin)."""
    token = get_tenant_token()
    r = requests.delete(
        f"{BASE_URL}/open-apis/drive/v1/files/{file_token}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params={"type": file_type}
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Delete error: {data}")
    return {"status": "deleted", "token": file_token}

# ── Doc: Copy ─────────────────────────────────────────────────────────────────

def doc_copy(doc_token: str, folder_token: str, title: str = None):
    """Copy a docx to another folder."""
    body = {"type": "docx", "folder_token": folder_token}
    if title:
        body["name"] = title
    r = _post(f"/open-apis/drive/v1/files/{doc_token}/copy", body)
    if r.get("code") != 0:
        raise RuntimeError(f"Doc copy error: {r}")
    return r.get("data", {}).get("file", {})

# ── Doc: Import from Markdown/HTML ────────────────────────────────────────────

def doc_import(content: str, file_name: str, folder_token: str, file_type: str = "md"):
    """Import markdown or docx content as a new Feishu document."""
    import tempfile, time
    token = get_tenant_token()
    suffix = ".md" if file_type == "md" else ".docx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    # Upload the temp file first
    upload_result = drive_upload(tmp_path, folder_token, file_name + suffix)
    os.unlink(tmp_path)
    file_token = upload_result.get("file_token")

    # Import the uploaded file
    r = _post("/open-apis/drive/v1/import_tasks", {
        "file_extension": file_type,
        "file_token": file_token,
        "type": "docx",
        "point": {"mount_type": 1, "mount_key": folder_token}
    })
    if r.get("code") != 0:
        raise RuntimeError(f"Import error: {r}")
    ticket = r.get("data", {}).get("ticket")

    # Poll for completion
    for _ in range(30):
        time.sleep(2)
        status = _get(f"/open-apis/drive/v1/import_tasks/{ticket}")
        job = status.get("data", {}).get("result", {})
        if job.get("job_status") == 0:  # success
            return {"doc_token": job.get("token"), "title": job.get("doc_name"), "url": job.get("url")}
        elif job.get("job_status") in [2, 3]:  # failed
            raise RuntimeError(f"Import failed: {job}")
    raise TimeoutError("Import timed out")

# ── Sheets: Create ────────────────────────────────────────────────────────────

def sheets_create(title: str, folder_token: str):
    """Create a new spreadsheet in a Drive folder."""
    r = _post("/open-apis/sheets/v3/spreadsheets", {
        "title": title,
        "folder_token": folder_token
    })
    if r.get("code") != 0:
        raise RuntimeError(f"Sheet create error: {r}")
    data = r.get("data", {}).get("spreadsheet", {})
    return {"token": data.get("spreadsheet_token"), "title": data.get("title"), "url": data.get("url")}

# ── Sheets: Get Meta ──────────────────────────────────────────────────────────

def sheets_meta(spreadsheet_token: str):
    """Get spreadsheet metadata including list of sheets."""
    r = _get(f"/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}")
    if r.get("code") != 0:
        raise RuntimeError(f"Sheet meta error: {r}")
    sp = r.get("data", {}).get("spreadsheet", {})
    sheets_r = _get(f"/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query")
    sheets = sheets_r.get("data", {}).get("sheets", [])
    return {
        "token": sp.get("spreadsheet_token"),
        "title": sp.get("title"),
        "url": sp.get("url"),
        "sheets": [{"id": s.get("sheet_id"), "title": s.get("title"), "index": s.get("index"),
                    "rows": s.get("grid_properties", {}).get("row_count"),
                    "cols": s.get("grid_properties", {}).get("column_count")} for s in sheets]
    }

# ── Sheets: Read Range ────────────────────────────────────────────────────────

def sheets_read(spreadsheet_token: str, range_str: str):
    """
    Read cell values from a sheet range.
    range_str format: "SheetID!A1:C10" or just "A1:C10" (uses first sheet)
    """
    r = _get(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{range_str}",
             params={"valueRenderOption": "ToString", "dateTimeRenderOption": "FormattedString"})
    if r.get("code") != 0:
        raise RuntimeError(f"Sheet read error: {r}")
    data = r.get("data", {}).get("valueRange", {})
    return {"range": data.get("range"), "values": data.get("values", [])}

# ── Sheets: Write Range ───────────────────────────────────────────────────────

def sheets_write(spreadsheet_token: str, range_str: str, values: list):
    """
    Write values to a sheet range.
    values: 2D list e.g. [["Name", "Score"], ["Alice", 95]]
    """
    r = _put(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values", {
        "valueRange": {"range": range_str, "values": values}
    })
    if r.get("code") != 0:
        raise RuntimeError(f"Sheet write error: {r}")
    return r.get("data", {})

def _put(path, body=None):
    r = requests.put(f"{BASE_URL}{path}", headers=_headers(), json=body or {})
    r.raise_for_status()
    return r.json()

# ── Sheets: Append Rows ───────────────────────────────────────────────────────

def sheets_append(spreadsheet_token: str, range_str: str, values: list):
    """Append rows after existing data in a range."""
    r = _post(f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_append", {
        "valueRange": {"range": range_str, "values": values},
        "insertDataOption": "INSERT_ROWS"
    })
    if r.get("code") != 0:
        raise RuntimeError(f"Sheet append error: {r}")
    return r.get("data", {})

# ── Sheets: Add Sheet ─────────────────────────────────────────────────────────

def sheets_add_sheet(spreadsheet_token: str, title: str):
    """Add a new sheet tab to a spreadsheet."""
    r = _post(f"/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/batch_create", {
        "requests": [{"add_sheet": {"properties": {"title": title}}}]
    })
    if r.get("code") != 0:
        raise RuntimeError(f"Add sheet error: {r}")
    replies = r.get("data", {}).get("replies", [])
    if replies:
        s = replies[0].get("add_sheet", {}).get("properties", {})
        return {"sheet_id": s.get("sheet_id"), "title": s.get("title")}
    return {}

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]

    def out(data):
        print(json.dumps(data, ensure_ascii=False, indent=2))

    if cmd == "token":
        out({"tenant_access_token": get_tenant_token()})

    elif cmd == "drive-search":
        query = args[1] if len(args) > 1 else ""
        out(drive_search(query))

    elif cmd == "drive-upload":
        out(drive_upload(args[1], args[2], args[3] if len(args) > 3 else None))

    elif cmd == "drive-delete":
        out(drive_delete(args[1], args[2]))

    elif cmd == "drive-copy":
        name = args[4] if len(args) > 4 else None
        out(drive_copy(args[1], args[2], args[3], name))

    elif cmd == "doc-copy":
        title = args[3] if len(args) > 3 else None
        out(doc_copy(args[1], args[2], title))

    elif cmd == "sheets-read":
        out(sheets_read(args[1], args[2]))

    elif cmd == "sheets-write":
        values = json.loads(args[3])
        out(sheets_write(args[1], args[2], values))

    elif cmd == "sheets-create":
        out(sheets_create(args[1], args[2]))

    elif cmd == "sheets-meta":
        out(sheets_meta(args[1]))

    elif cmd == "sheets-add-sheet":
        out(sheets_add_sheet(args[1], args[2]))

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

if __name__ == "__main__":
    main()
