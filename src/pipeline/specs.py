"""Specs data collection pipeline — fetches config tables and writes to database."""
import time
import re
from datetime import datetime
from collections import defaultdict

from openpyxl.cell.rich_text import TextBlock, CellRichText
from openpyxl.cell.text import InlineFont

from ..api import (
    fetch_brand_map, fetch_brand_index, fetch_series, fetch_series_by_level,
    get_param_config, get_latest_month,
)
from ..brands import CATEGORIES, clean_manu_name, create_manu_map, resolve_brands
from ..db import upsert_brand, upsert_series, insert_spec_year, replace_spec_params, insert_spec_names

ONLY_ON_SALE = True


def run(conn, mode="sales"):
    """Collect config specs and write to database.

    Args:
        conn: sqlite3.Connection
        mode: "sales" (default, hot-selling series) or "all" (all brands)
    """
    today = datetime.now().strftime("%Y-%m-%d")

    print("=== Step 1: Fetching brand index ===")
    brand_map = fetch_brand_map()
    manu_map = create_manu_map(brand_map)

    print("=== Step 2: Collecting series list ===")
    if mode == "all":
        brands = fetch_brand_index()
        all_series = {}
        for b in brands:
            for m in b["manufacturers"]:
                for s in m["series"]:
                    sid = int(s["seriesid"])
                    if sid not in all_series:
                        all_series[sid] = {
                            "name": s["name"],
                            "brandid": b["brandid"],
                        }
        total = len(all_series)
    else:
        all_series = _build_series_from_categories()
        total = len(all_series)

    print(f"Collected {total} unique series")

    # Resolve brands for "sales" mode
    if mode == "sales":
        series_by_brand = defaultdict(list)
        for sid, info in all_series.items():
            bid = info["brandid"]
            if bid:
                series_by_brand[bid].append(str(sid))
        resolve_brands(brand_map, manu_map, series_by_brand)

    # Write brands
    for brandid, brand_name in brand_map.items():
        manu = manu_map.get(brandid, brand_name)
        upsert_brand(conn, brandid, brand_name, manu, today)

    print(f"\n=== Step 3: Fetching config for {total} series ===")
    stats = {"success": 0, "empty": 0, "error": 0, "skipped": 0}

    for i, (sid, info) in enumerate(sorted(all_series.items()), 1):
        series_name = info["name"]
        brandid = info["brandid"]
        brand_name = brand_map.get(brandid, f"品牌{brandid}")
        manu = manu_map.get(brandid, clean_manu_name(brand_name))

        # Check if this series already has config data in DB
        existing = conn.execute(
            "SELECT count(*) FROM spec_years WHERE seriesid=?", (sid,)
        ).fetchone()[0]
        if existing > 0:
            stats["skipped"] += 1
            if stats["skipped"] % 50 == 0:
                print(f"  skipped {stats['skipped']} existing series...")
            continue

        print(f"  [{i}/{total}] {series_name} (sid={sid})", end=" ")

        result = get_param_config(sid)
        if not result:
            print("ERROR")
            stats["error"] += 1
            time.sleep(0.3)
            continue

        config_data, _ = parse_config(result)
        if not config_data:
            print("no on-sale data" if ONLY_ON_SALE else "empty")
            stats["empty"] += 1
            time.sleep(0.3)
            continue

        # Upsert series metadata
        upsert_series(conn, sid, brandid, series_name, "", "", "在售")

        # Write spec data
        for year_name, (spec_names, param_rows) in config_data.items():
            sy_id = insert_spec_year(conn, sid, year_name, len(spec_names), today)
            if sy_id is None:
                continue
            params = _flatten_params(param_rows, len(spec_names))
            replace_spec_params(conn, sy_id, params)
            insert_spec_names(conn, sy_id, spec_names)

        years = list(config_data.keys())
        print(f"-> {len(years)} years: {', '.join(years)} | {manu}/{brand_name}/{series_name}")
        stats["success"] += 1
        time.sleep(0.15)

    print(f"\nDone: {stats['success']} success, {stats['empty']} empty, "
          f"{stats['error']} errors, {stats['skipped']} skipped")


def _build_series_from_categories():
    """Build series list from CATEGORIES (same logic as fetch_specs.py sales mode)."""
    all_series = {}
    for cat_big, subcats in CATEGORIES.items():
        for sub_name, levelid in subcats:
            items = fetch_series(levelid, get_latest_month())
            if items:
                for item in items:
                    sid = int(item.get("seriesid", 0))
                    if sid and sid not in all_series:
                        all_series[sid] = {
                            "name": item.get("seriesname", ""),
                            "brandid": item.get("brandid", 0),
                        }
            else:
                series_map = fetch_series_by_level(levelid)
                for sid_str, s_info in series_map.items():
                    sid = int(sid_str)
                    if sid not in all_series:
                        all_series[sid] = {
                            "name": s_info["name"],
                            "brandid": s_info.get("brandid", 0),
                        }
            time.sleep(0.2)
    return all_series


def _param_value(param_item):
    """Extract display value from a paramconflist item (inlined from fetch_specs.py)."""
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


def _flatten_params(param_rows, num_specs):
    """Convert param_rows [(group, pname, [values...]), ...] into flat (group, pname, index, value) tuples."""
    flat = []
    for group_name, pname, values in param_rows:
        for i in range(num_specs):
            val = values[i] if i < len(values) else "-"
            # Convert CellRichText to plain string
            if hasattr(val, "items"):
                parts = []
                for item in val.items:
                    if hasattr(item, "text"):
                        parts.append(item.text)
                val = "".join(parts)
            flat.append((group_name, pname, i, str(val) if val is not None else "-"))
    return flat
