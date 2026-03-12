# helpers/excel.py
import os
from openpyxl import load_workbook, Workbook
from openpyxl.styles import PatternFill, Font

def prepare_workbook_for_append(output_file: str, headers: list, category_sheets=("Music","Navigation","Messaging")):
    out_dir = os.path.dirname(output_file)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(output_file):
        Workbook().save(output_file)

    wb = load_workbook(output_file)
    bold_font = Font(bold=True)

    ws_map = {}
    for name in category_sheets:
        if name in wb.sheetnames:
            ws = wb[name]
            if ws.max_row == 0 or any(ws.cell(row=1, column=j).value in (None, "") for j in range(1, len(headers)+1)):
                for j, h in enumerate(headers, start=1):
                    c = ws.cell(row=1, column=j, value=h)
                    c.font = bold_font
        else:
            ws = wb.create_sheet(name)
            for j, h in enumerate(headers, start=1):
                c = ws.cell(row=1, column=j, value=h)
                c.font = bold_font
        ws_map[name] = ws

    if "Sheet" in wb.sheetnames and "Sheet" not in ws_map:
        ws0 = wb["Sheet"]
        if ws0.max_row <= 1 and ws0.max_column <= 1 and (ws0["A1"].value in (None, "")):
            wb.remove(ws0)

    return wb, ws_map


def append_rows_to_category_sheets(ws_map: dict, rows_out: list, file_category: str, *, input_dir=None, base_url: str = ""):
    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")

    def _to_hyperlink(source_path: str):
        if not source_path:
            return None, ""
        sp_norm = os.path.abspath(source_path)
        if base_url:
            try:
                rel = os.path.relpath(sp_norm, start=os.path.abspath(input_dir or os.getcwd()))
                rel_url = "/".join(rel.split(os.sep))
                return f"{base_url.rstrip('/')}/{rel_url}", sp_norm
            except Exception:
                return "file:///" + sp_norm.replace("\\", "/"), sp_norm
        return "file:///" + sp_norm.replace("\\", "/"), sp_norm

    def _is_http_url(s: str) -> bool:
        return bool(s and s.strip().lower().startswith(("http://", "https://")))

    # If file category matches a known sheet, use it; otherwise classify per row (done upstream)
    for row in rows_out:
        target_cat = file_category if file_category in ws_map else row[0]  # overwritten later in pipeline; kept for safety
        # We'll rely on caller to give the correct sheet via ws_map; if not, try guesses:
        if target_cat not in ws_map:
            # Attempt auto based on content classification (the caller may have embedded this)
            # To keep helpers decoupled, we just skip if unknown
            continue

        ws = ws_map[target_cat]
        i = ws.max_row + 1

        # Write cells + hyperlinks
        for j, val in enumerate(row, start=1):
            cell = ws.cell(row=i, column=j, value=val)
            # App Link (col 7)
            if j == 7 and isinstance(val, str) and _is_http_url(val):
                cell.hyperlink = val.strip()
                cell.style = "Hyperlink"
            # Source (col 8)
            if j == 8 and isinstance(val, str) and val.strip():
                url, display = _to_hyperlink(val.strip())
                if url:
                    cell.value = display
                    cell.hyperlink = url
                    cell.style = "Hyperlink"

        # Highlight Rank == 1 (col 4)
        try:
            rank_int = int(str(row[3]).strip())
        except Exception:
            rank_int = None

        if rank_int == 1:
            for col_idx in range(1, len(row) + 1):
                ws.cell(row=i, column=col_idx).fill = yellow_fill