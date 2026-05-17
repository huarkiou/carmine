"""Collect autohome parameter config tables for all series, organized by manufacturer/brand/model."""
import time
import re
import os
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from openpyxl.cell.rich_text import TextBlock, CellRichText
from openpyxl.cell.text import InlineFont

from .api import fetch_brand_map, fetch_series, fetch_series_by_level, get_param_config, get_latest_month
from .brands import clean_manu_name, create_manu_map, resolve_brands
from .excel_writer import write_config_xlsx

OUTPUT_DIR = os.environ.get("CARMIINE_OUTPUT", "D:/Projects/Program/carmine/output")
ONLY_ON_SALE = True  # True=仅在售年款, False=全部年款

# Category selection mode:
#   "sales" → top-selling series only (uses brands.CATEGORIES: 轿车/SUV/MPV)
#   "all"   → all categories including 跑车/皮卡/微卡/轻客/微面
#   "跑车,皮卡" → only specified categories (comma-separated env var)
CATEGORY_MODE = os.environ.get("CARMIINE_MODE", "sales")

_DATA_DIR = Path(__file__).parent / "data"


def _load_categories(mode):
    """Load category definitions based on mode."""
    from .brands import CATEGORIES
    if mode == "sales":
        return CATEGORIES
    if mode == "all":
        with open(_DATA_DIR / "all_categories.json", "r", encoding="utf-8") as f:
            return json.load(f)
    # comma-separated string → list
    names = [n.strip() for n in mode.split(",") if n.strip()]
    if names:
        with open(_DATA_DIR / "all_categories.json", "r", encoding="utf-8") as f:
            all_cats = json.load(f)
        return {k: v for k, v in all_cats.items() if k in names}
    return CATEGORIES


def build_series_list(categories):
    """Build series list from categories, falling back to price API for categories without rank data."""
    all_series = {}
    for cat_big, subcats in categories.items():
        for sub_name, levelid in subcats:
            items = fetch_series(levelid, get_latest_month())
            if items:
                for item in items:
                    sid = str(item.get("seriesid", ""))
                    if sid and sid not in all_series:
                        all_series[sid] = {
                            "name": item.get("seriesname", ""),
                            "brandid": item.get("brandid", 0),
                        }
            else:
                # Fallback: fetch from price page
                series_map = fetch_series_by_level(levelid)
                for sid, info in series_map.items():
                    if sid not in all_series:
                        all_series[sid] = {
                            "name": info["name"],
                            "brandid": info.get("brandid", 0),
                            "fctname": info.get("fctname", ""),
                        }
            time.sleep(0.2)
    print(f"Collected {len(all_series)} unique series")
    return all_series


def _param_value(param_item):
    """Extract display value from a paramconflist item.
    
    Returns str or CellRichText (for color params).
    """
    # Color info: return rich text with each color name in its own hex color
    ci = param_item.get("colorinfo")
    if ci and isinstance(ci, dict) and ci.get("list"):
        blocks = []
        for i, c in enumerate(ci["list"]):
            name = c.get("name", "")
            hex_color = (c.get("value") or "").lstrip("#")
            if not name:
                continue
            if i > 0:
                blocks.append(TextBlock(InlineFont(), "\n"))
            # Handle mixed colors like "黑色/雪隐灰" with "#000000/#E7DDD5"
            if "/" in name and "/" in hex_color:
                name_parts = name.split("/")
                hex_parts = [h.lstrip("#") for h in hex_color.split("/")]
                for j, (np, hp) in enumerate(zip(name_parts, hex_parts)):
                    if j > 0:
                        blocks.append(TextBlock(InlineFont(), "/"))
                    try:
                        blocks.append(TextBlock(InlineFont(color="FF" + hp.strip() if hp.strip() else "FF000000"), np.strip()))
                    except Exception:
                        blocks.append(TextBlock(InlineFont(), np.strip()))
            else:
                try:
                    blocks.append(TextBlock(InlineFont(color="FF" + hex_color if hex_color else "FF000000"), name))
                except Exception:
                    blocks.append(TextBlock(InlineFont(), name))
        if blocks:
            return CellRichText(*blocks)
    # Sublist: use sub-item names joined by newlines
    sl = param_item.get("sublist")
    if sl and isinstance(sl, list) and sl:
        parts = []
        for sub in sl:
            if isinstance(sub, dict):
                name = sub.get("name", "")
                value = sub.get("value", "")
                if name:
                    parts.append(f"{name}: {value}" if value else name)
        if parts:
            return "\n".join(parts)
    # Default: plain itemname, or "-" if truly empty
    val = param_item.get("itemname")
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return "-"
    return str(val)


def parse_config(result):
    """Parse getParamConf API result into {year_name: (spec_names, param_rows)}."""
    titlelist = result.get("titlelist", [])
    datalist = result.get("datalist", [])
    conditionlist = result.get("conditionlist", [])

    year_options = {}
    for cond in conditionlist:
        if cond.get("typevalue") == "year":
            for y in cond.get("list", []):
                if not ONLY_ON_SALE or y.get("lazyload") == 0:
                    year_options[y.get("id")] = y.get("name", "")

    year_specs = defaultdict(list)
    for spec in datalist:
        cond = spec.get("condition", [])
        spec_year = cond[-1] if isinstance(cond, list) and cond else ""
        if not spec_year or not spec_year.isdigit() or spec_year not in year_options:
            continue
        year_specs[spec_year].append(spec)

    output = {}
    for year_id, specs in year_specs.items():
        year_name = year_options.get(year_id, f"{year_id}款")
        param_rows = []
        for group in titlelist:
            group_name = group.get("itemtype", "")
            for item in group.get("items", []):
                tid = item.get("titleid")
                pname = item.get("itemname", "")
                values = []
                for spec in specs:
                    val = ""
                    for p in spec.get("paramconflist", []):
                        if p.get("titleid") == tid:
                            val = _param_value(p)
                            break
                    values.append(val)
                param_rows.append((group_name, pname, values))
        spec_names = [s.get("specname", "") for s in specs]
        output[year_name] = (spec_names, param_rows)

    return output, year_options


def main():
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]  # YYYYMMDDHHMMSSmmm
    output_dir = os.path.join(OUTPUT_DIR, ts)
    print(f"Output directory: {output_dir}")
    print("=== Step 1: Fetching brand list ===")
    brand_map = fetch_brand_map()
    manu_map = create_manu_map(brand_map)

    print("=== Step 2: Collecting all series ===")
    categories = _load_categories(CATEGORY_MODE)
    all_series = build_series_list(categories)
    series_by_brand = defaultdict(list)
    for sid, info in all_series.items():
        bid = info["brandid"]
        if bid:
            series_by_brand[bid].append(sid)

    print("=== Step 3: Resolving brand names ===")
    resolve_brands(brand_map, manu_map, series_by_brand)

    print(f"\n=== Step 4: Fetching config for {len(all_series)} series ===")
    stats = {"success": 0, "empty": 0, "error": 0, "skipped": 0}

    for i, (sid, info) in enumerate(sorted(all_series.items())):
        series_name = info["name"]
        brandid = info["brandid"]
        brand_name = brand_map.get(brandid, f"品牌{brandid}")
        manufacturer = manu_map.get(brandid, clean_manu_name(brand_name))

        safe_name = re.sub(r'[\\/:*?"<>|]', '_', series_name)
        dir_path = os.path.join(output_dir, manufacturer, brand_name)
        filepath = os.path.join(dir_path, f"{safe_name}.xlsx")

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

        print(f"  [{i+1}/{len(all_series)}] {series_name} (sid={sid})", end=" ")

        result = get_param_config(sid)
        if not result:
            print("ERROR")
            stats["error"] += 1
            time.sleep(0.3)
            continue

        config_data, year_options = parse_config(result)
        if not config_data:
            print("no on-sale data" if ONLY_ON_SALE else "empty")
            stats["empty"] += 1
            time.sleep(0.3)
            continue

        os.makedirs(dir_path, exist_ok=True)
        ok = write_config_xlsx(filepath, config_data)
        if ok:
            years = list(config_data.keys())
            print(f"-> {len(years)} years: {', '.join(years)} | {manufacturer}/{brand_name}/{safe_name}.xlsx")
            stats["success"] += 1
        else:
            print("WRITE ERROR")
            stats["error"] += 1

        time.sleep(0.15)

    print(f"\nDone: {stats['success']} success, {stats['empty']} empty, {stats['error']} errors, {stats['skipped']} skipped")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
