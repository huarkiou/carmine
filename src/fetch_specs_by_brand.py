"""Collect autohome param config tables for ALL brands via grade/carhtml index.

Independent of fetch_specs.py — uses brand index pages instead of sales ranking categories.
"""
import time
import re
import os
from datetime import datetime
from collections import defaultdict

from .api import fetch_brand_index, get_param_config
from .brands import clean_manu_name
from .excel_writer import write_config_xlsx

OUTPUT_DIR = os.environ.get("CARMIINE_OUTPUT", "D:/Projects/Program/carmine/output")
ONLY_ON_SALE = True  # True=仅在售年款, False=全部年款


def _parse_config(result):
    """Reuse parse_config logic from fetch_specs (inlined to avoid coupling).
    
    Returns {year_name: (spec_names, param_rows)} or empty dict if no on-sale data.
    """
    from .fetch_specs import parse_config
    return parse_config(result)


def main():
    ts = datetime.now().strftime("%Y%m%d%H%M")
    output_dir = os.path.join(OUTPUT_DIR, ts)
    print(f"Output directory: {output_dir}")

    print("=== Step 1: Fetching brand index ===")
    brands = fetch_brand_index()

    print("=== Step 2: Fetching config for all series ===")
    stats = {"success": 0, "empty": 0, "error": 0, "skipped": 0}
    total_series = sum(
        len(s) for b in brands for m in b["manufacturers"] for s in m["series"]
    )
    idx = 0

    for brand in brands:
        brand_name = brand["brand_name"]
        brandid = brand["brandid"]

        for manu in brand["manufacturers"]:
            manu_name = clean_manu_name(manu["name"])

            for series in manu["series"]:
                idx += 1
                sid = series["seriesid"]
                series_name = series["name"]

                safe_name = re.sub(r'[\\/:*?"<>|]', '_', series_name)
                dir_path = os.path.join(output_dir, manu_name, brand_name)
                filepath = os.path.join(dir_path, f"{safe_name}.xlsx")

                # Resume: skip existing files (unless broken .tmp remains)
                if os.path.exists(filepath):
                    tmp_path = filepath + ".tmp"
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                        os.remove(filepath)
                    else:
                        stats["skipped"] += 1
                        if stats["skipped"] % 50 == 0:
                            print(f"  skipped {stats['skipped']} existing files...")
                        continue

                print(f"  [{idx}/{total_series}] {series_name} (sid={sid})", end=" ")

                result = get_param_config(sid)
                if not result:
                    print("ERROR")
                    stats["error"] += 1
                    time.sleep(0.3)
                    continue

                config_data, _ = _parse_config(result)
                if not config_data:
                    print("no on-sale data" if ONLY_ON_SALE else "empty")
                    stats["empty"] += 1
                    time.sleep(0.3)
                    continue

                os.makedirs(dir_path, exist_ok=True)
                ok = write_config_xlsx(filepath, config_data)
                if ok:
                    years = list(config_data.keys())
                    print(f"-> {len(years)} years: {', '.join(years)} | {manu_name}/{brand_name}/{safe_name}.xlsx")
                    stats["success"] += 1
                else:
                    print("WRITE ERROR")
                    stats["error"] += 1

                time.sleep(0.15)

    print(f"\nDone: {stats['success']} success, {stats['empty']} empty, "
          f"{stats['error']} errors, {stats['skipped']} skipped")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
