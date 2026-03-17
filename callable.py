# run_directory.py
import os
import sys
import argparse
from datetime import datetime

from scraper_helpers.io import load_config, html_from_mhtml_bytes, safe_filename
from scraper_helpers.console import (
    clear_screen, prompt_input, progress_bar, iter_mhtml_files,
    effective_cap, post_trim_rows
)
from scraper_helpers.mhtml_images import build_icon_lookup
from scraper_helpers.excel import prepare_workbook_for_append, append_rows_to_category_sheets
from scraper_models.constants import HEADERS
from scraper_detectors.platform import detect_platform_from_filename
from scraper_detectors.country import detect_country_from_filename
from scraper_detectors.category import detect_category_from_filename
from scraper_pipeline.dispatcher import extract_platform_rows, build_output_rows


DEBUG = False
def dbg(*args):
    if DEBUG:
        print("[debug]", *args)


def run_batch_directory(
    directory: str,
    quarter: str,
    output_dir: str,
    output_filename: str = "output.xlsx",
    debug: bool = False
):
    global DEBUG
    DEBUG = bool(debug)

    if not directory or not os.path.isdir(directory):
        raise ValueError(f"Invalid directory: {directory!r}")

    # ---- Load config and compute caps ----
    config = load_config()
    cap = effective_cap(config.get("max_rows", 10))
    dbg("row cap:", cap)

    # ---- Enumerate files ----
    files = list(iter_mhtml_files(directory))
    files.sort(key=lambda p: os.path.basename(p).lower())
    if not files:
        raise ValueError(f"No .mhtml/.mht files found in: {directory}")

    # ---- Prepare output ----
    if not output_dir:
        # default to ./log_YYYY-MM-DD
        today = datetime.now().strftime("%Y-%m-%d")
        output_dir = os.path.join(os.getcwd(), f"log_{today}")
    os.makedirs(output_dir, exist_ok=True)

    if not output_filename:
        output_filename = "output.xlsx"

    outfile = os.path.join(output_dir, safe_filename(output_filename, ext=".xlsx"))

    # ---- Prepare workbook once ----
    wb, ws_map = prepare_workbook_for_append(
        outfile,
        headers=HEADERS,
        category_sheets=("Music", "Navigation", "Messaging")
    )
    base_url = (config.get("source_base_url") or "").strip()

    # ---- Process files ----
    failures = 0
    messages = []

    for idx, path in enumerate(files, start=1):
        base = os.path.basename(path)
        try:
            if DEBUG:
                progress_bar(idx - 1, len(files))

            # 1) Detect platform/country/category from filename
            platform_key = detect_platform_from_filename(path)
            country_code = detect_country_from_filename(path)
            file_category = detect_category_from_filename(path)
            if not platform_key:
                msg = f"{base}: No platform hint from filename. Skipping."
                messages.append("⚠ " + msg)
                failures += 1
                continue

            # 2) Parse MHTML -> HTML
            with open(path, "rb") as f:
                raw_mhtml = f.read()
            html, err = html_from_mhtml_bytes(raw_mhtml)
            if err or not html:
                msg = f"{base}: {err or 'Failed to parse MHTML'}"
                messages.append("✖ " + msg)
                failures += 1
                continue
            icon_lookup = build_icon_lookup(raw_mhtml)

            # 3) Extract rows using dispatcher (platform-specific extractors)
            plat_name, rows, reason = extract_platform_rows(
                platform_key, html, config, max_rows=cap, source_path=path
            )
            rows = post_trim_rows(rows, cap)
            if not rows:
                msg = f"{base}: 0 rows from {platform_key} ({reason})"
                messages.append("✖ " + msg)
                failures += 1
                continue

            # 4) Map to your fixed schema
            final_rows = build_output_rows(
                plat_name,
                rows,
                country_code,
                quarter or "Unknown",
                path
            )

            # 5) Append to Excel sheets
            append_rows_to_category_sheets(ws_map, final_rows, file_category, input_dir=directory, base_url=base_url, icon_lookup=icon_lookup, )

            if DEBUG:
                progress_bar(idx, len(files))

            ok_msg = (f"{base}: {len(final_rows)} rows → {plat_name}"
                      + (f" (category: {file_category})" if file_category else "")
                      + (f" (country: {country_code})" if country_code else ""))
            messages.append("✔ " + ok_msg)

        except Exception as e:
            messages.append(f"✖ {base}: Exception: {e}")
            failures += 1

    # 6) Save once
    try:
        wb.save(outfile)
    except Exception as e:
        raise Exception(f"Failed to save workbook '{outfile}': {e}")

    # summarize counts per sheet
    by_category = {}
    for cat in ["Music", "Navigation", "Messaging"]:
        ws = ws_map.get(cat)
        count = (ws.max_row - 1) if ws and ws.max_row else 0
        by_category[cat] = count

    return {
        "processed": len(files),
        "failures": failures,
        "output_path": outfile,
        "by_category": by_category,
        "messages": messages,
    }


# =======================
# Existing interactive mode
# =======================

def run_directory_mode():
    """
    Interactive filename-first run:
      - Detect platform/country/category from filename
      - Parse MHTML → HTML
      - Extract top rows per platform
      - Append to category sheets in a single workbook
    """
    clear_screen()
    print("==============================================")
    print("   Batch MHTML Scraper - Filename-First Mode")
    print("==============================================\n")

    config = load_config()
    cap = effective_cap(config.get("max_rows", 10))
    dbg("row cap:", cap)

    dir_path = prompt_input("Enter the directory containing .mhtml/.mht files")
    if not os.path.isdir(dir_path):
        print(f"❌ Error: Not a directory: {dir_path}")
        sys.exit(1)

    files = list(iter_mhtml_files(dir_path))
    files.sort(key=lambda p: os.path.basename(p).lower())
    if not files:
        print(f"❌ No .mhtml/.mht files found in: {dir_path}")
        sys.exit(1)

    quarter_str = prompt_input("Enter Quarter (e.g., 2026 Q1 or 2026Q1)")

    today = datetime.now().strftime("%Y-%m-%d")
    default_out = os.path.join(os.getcwd(), f"log_{today}")
    out_dir = prompt_input("Output directory", default=default_out)
    os.makedirs(out_dir, exist_ok=True)

    output_filename = "output.xlsx"
    outfile = os.path.join(out_dir, safe_filename(output_filename, ext=".xlsx"))

    # Use the new API function
    result = run_batch_directory(
        directory=dir_path,
        quarter=quarter_str,
        output_dir=out_dir,
        output_filename=os.path.basename(outfile),
        debug=DEBUG
    )

    # Print summary
    print("\n📝 Wrote workbook:", result["output_path"])
    print("\n✅ Done.")
    print(f"   • Files processed: {result['processed']} (failures: {result['failures']})")
    print(f"   • Output folder: {out_dir}")


def run_directory_non_interactive(args):
    """
    Non-interactive filename-first run:
      --dir, --quarter, --output-dir
    """
    global DEBUG
    DEBUG = bool(args.debug)

    # Use the new API function
    result = run_batch_directory(
        directory=args.dir,
        quarter=args.quarter or "Unknown",
        output_dir=args.output_dir or os.path.join(os.getcwd(), f"log_{datetime.now().strftime('%Y-%m-%d')}"),
        output_filename="output.xlsx",
        debug=DEBUG
    )

    print(f"Wrote: {result['output_path']}")
    for cat, count in result["by_category"].items():
        print(f"  - {cat}: {count} row(s)")
    print(f"Success: processed={result['processed']} failures={result['failures']} out_dir={os.path.dirname(result['output_path'])}")


def main():
    parser = argparse.ArgumentParser(
        description=("Batch MHTML scraper (filename-first) → one Excel with Music/Navigation/Messaging sheets.")
    )
    parser.add_argument("--dir", help="Directory containing .mhtml/.mht files.", default=None)
    parser.add_argument("--quarter", help="Quarter label, e.g., '2026 Q1'.", default=None)
    parser.add_argument("--output-dir", help="Output directory (default: ./log_YYYY-MM-DD).", default=None)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    global DEBUG
    if args.debug:
        DEBUG = True

    if args.dir:
        run_directory_non_interactive(args)
    else:
        run_directory_mode()


if __name__ == "__main__":
    main()