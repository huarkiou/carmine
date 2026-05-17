"""Brand-to-manufacturer mapping, name cleaning, and lookup logic."""
import json
import time
from pathlib import Path
from collections import defaultdict

import json5

_DATA_DIR = Path(__file__).parent / "data"


def _load_jsonc(path):
    with open(path, "r", encoding="utf-8") as f:
        return json5.load(f)


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Vehicle category definitions loaded from data file
CATEGORIES = _load_json(_DATA_DIR / "categories.json")

MONTHS = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]

# brand_name -> manufacturer_name loaded from data file
BRAND_TO_MANUFACTURER = _load_jsonc(_DATA_DIR / "brand_manufacturer.jsonc")


def clean_manu_name(name):
    """Strip common suffixes (汽车制造厂, 汽车, 集团) from manufacturer names."""
    if not name:
        return name
    for suffix in ["汽车制造厂", "汽车", "集团"]:
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[:-len(suffix)]
    return name


def create_manu_map(brand_map):
    """Map brandid -> manufacturer using explicit BRAND_TO_MANUFACTURER, with fallback to cleaning."""
    result = {}
    for brandid, brand_name in brand_map.items():
        manu = BRAND_TO_MANUFACTURER.get(brand_name)
        if not manu:
            for key in BRAND_TO_MANUFACTURER:
                if key in brand_name or brand_name in key:
                    manu = BRAND_TO_MANUFACTURER[key]
                    break
        if not manu:
            manu = clean_manu_name(brand_name)
        result[brandid] = manu
    return result


def fill_missing_brands(brand_map, manu_map, series_by_brand):
    """Query series detail pages for brands not found in brand ranking API."""
    from .api import lookup_brand_from_series

    missing = {bid for bid in series_by_brand if bid not in brand_map}
    if not missing:
        return
    print(f"Filling {len(missing)} missing brands from series detail pages...")
    for brandid in sorted(missing):
        sid = series_by_brand[brandid][0]
        bname, manu = lookup_brand_from_series(brandid, sid)
        if bname:
            brand_map[brandid] = bname
            if manu:
                manu_map[brandid] = manu
            print(f"  brandid={brandid}: brand={bname}, manu={manu}")
        time.sleep(0.3)


def resolve_brands(brand_map, manu_map, series_by_brand):
    """Complete brand resolution pipeline: fetch -> map -> fill missing -> re-apply mapping."""
    previously_missing = {bid for bid in series_by_brand if bid not in brand_map}
    fill_missing_brands(brand_map, manu_map, series_by_brand)
    new_manu = create_manu_map(brand_map)
    for bid in previously_missing:
        if bid in new_manu:
            manu_map[bid] = new_manu[bid]
    return previously_missing
