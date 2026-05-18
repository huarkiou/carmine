# Brand-Based Spec Fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `fetch_specs_by_brand.py` — an independent script that enumerates all autohome brands via grade/carhtml pages, fetches config specs for every on-sale series, and outputs `主机厂/品牌/车型.xlsx`.

**Architecture:** One new API function (`fetch_brand_index`) parses 26 grade/carhtml pages to build a `brand → manufacturer → series` tree. One new orchestration script iterates that tree, calls existing `get_param_config`/`parse_config`/`write_config_xlsx` per series. No changes to existing scripts.

**Tech Stack:** Python 3.10+, requests, re, openpyxl (all already in project).

---

### Task 1: Add `fetch_brand_index()` to `src/api.py`

**Files:**
- Modify: `src/api.py` (append new function at end)

- [ ] **Step 1: Implement `fetch_brand_index()`**

Add to end of `src/api.py`, before the last blank line:

```python
def fetch_brand_index():
    """Parse grade/carhtml/{A-Z}.html pages to build brand->manufacturer->series tree.
    
    Returns list of dicts:
        [{brandid, brand_name, manufacturers: [{name, series: [{seriesid, name}]}]}]
    """
    result = []
    seen_series = set()
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        url = f"https://www.autohome.com.cn/grade/carhtml/{letter}.html"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.encoding = "gb2312"
        except Exception as e:
            print(f"  Failed to fetch {url}: {e}")
            continue

        html = r.text
        # Each brand is a <dl id="BRANDID">...</dl> block
        dl_pattern = re.compile(r'<dl id="(\d+)"(.*?)</dl>', re.DOTALL)
        for m in dl_pattern.finditer(html):
            brandid = int(m.group(1))
            section = m.group(2)

            # Brand name from <dt><div><a>...
            brand_name = ""
            bm = re.search(r'<dt>.*?<div><a.*?>(.*?)</a>', section, re.DOTALL)
            if bm:
                brand_name = bm.group(1).strip()

            # Manufacturers: each <div class="h3-tit"><a>FCT</a></div>
            # followed by <ul class="rank-list-ul"> with <li id="sSERIESID"> series
            # Split by h3-tit boundaries
            parts = re.split(r'(<div class="h3-tit">.*?</div>)', section)
            current_fct = ""
            manufacturers = []
            fct_series = []  # (fct_name, series_list)

            for part in parts:
                fct_m = re.search(r'class="h3-tit"><a.*?>(.*?)</a>', part)
                if fct_m:
                    # Flush previous fct if it had series
                    if current_fct and fct_series:
                        manufacturers.append({"name": current_fct, "series": fct_series})
                        fct_series = []
                    current_fct = fct_m.group(1).strip()
                else:
                    # Look for series in this part
                    for sm in re.finditer(r'<li id="s(\d+)".*?<h4><a.*?>(.*?)</a>', part, re.DOTALL):
                        sid = sm.group(1)
                        sname = sm.group(2).strip()
                        if sid not in seen_series:
                            fct_series.append({"seriesid": sid, "name": sname})
                            seen_series.add(sid)

            # Flush last fct
            if current_fct and fct_series:
                manufacturers.append({"name": current_fct, "series": fct_series})

            if brand_name and manufacturers:
                result.append({
                    "brandid": brandid,
                    "brand_name": brand_name,
                    "manufacturers": manufacturers,
                })

        time.sleep(0.2)

    total_series = sum(
        len(s) for b in result for m in b["manufacturers"] for s in m["series"]
    )
    print(f"Brand index: {len(result)} brands, {total_series} series")
    return result
```

- [ ] **Step 2: Commit**

```bash
git add src/api.py
git commit -m "feat: add fetch_brand_index() to parse grade/carhtml brand pages"
```

---

### Task 2: Create `src/fetch_specs_by_brand.py`

**Files:**
- Create: `src/fetch_specs_by_brand.py`

- [ ] **Step 1: Write the full script**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add src/fetch_specs_by_brand.py
git commit -m "feat: add fetch_specs_by_brand.py for brand-index-based config collection"
```

---

### Task 3: Verify

- [ ] **Step 1: Dry-run a minimal brand fetch to confirm parsing works**

```bash
uv run python -c "
from src.api import fetch_brand_index
brands = fetch_brand_index()
print(f'Brands: {len(brands)}')
for b in brands[:3]:
    print(f'  {b[\"brand_name\"]} (id={b[\"brandid\"]}): {len(b[\"manufacturers\"])} manufacturers')
    for m in b['manufacturers'][:2]:
        print(f'    {m[\"name\"]}: {len(m[\"series\"])} series')
        for s in m['series'][:2]:
            print(f'      {s[\"seriesid\"]} {s[\"name\"]}')
"
```

Expected: prints all 26 letters worth of brands (should be ~600+ brands, thousands of series).

- [ ] **Step 2: Verify it can run standalone (dry-run only a few series)**

Comment out the full loop or set a break after 3 series to confirm the pipeline: brand index → config fetch → xlsx write works end-to-end.

- [ ] **Step 3: Review parse_config import**

Check that `from .fetch_specs import parse_config` works correctly — `parse_config` references `_param_value` which is module-level in `fetch_specs.py` and must be importable.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: address issues found during verification"
```
