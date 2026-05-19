# Database Export to xlsx Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `export` module to read from SQLite and produce xlsx files matching the original output format, with configurable sales parameters.

**Architecture:** `export.py` CLI dispatches to `export/sales.py` and `export/specs.py`, which query the database via raw SQL and feed results into the existing `excel_writer.py` functions. Also adds `spec_names` table to database schema to preserve configuration version names for accurate export.

**Tech Stack:** Python 3.10+, sqlite3, openpyxl, argparse (all already in project).

---

### Task 1: Add `spec_names` table and migration to `src/db.py`

**Files:**
- Modify: `src/db.py`

- [ ] **Step 1: Add `spec_names` table to SCHEMA**

After the `spec_params` CREATE TABLE, add:

```python
CREATE TABLE IF NOT EXISTS spec_names (
    spec_year_id INTEGER NOT NULL REFERENCES spec_years(id),
    spec_index   INTEGER NOT NULL,
    spec_name    TEXT,
    PRIMARY KEY (spec_year_id, spec_index)
);
```

- [ ] **Step 2: Add `insert_spec_names()` function**

```python
def insert_spec_names(conn, spec_year_id, names):
    """Insert or replace spec names for a given spec_year_id.
    
    Args:
        conn: sqlite3.Connection
        spec_year_id: int
        names: list of str, indexed by spec_index (names[i] = spec name for column i)
    """
    conn.executemany(
        "INSERT OR REPLACE INTO spec_names (spec_year_id, spec_index, spec_name) VALUES (?, ?, ?)",
        [(spec_year_id, i, name) for i, name in enumerate(names)]
    )
    conn.commit()
```

- [ ] **Step 3: Verify**

```bash
uv run python -c "
from src.db import init_db, insert_spec_year, insert_spec_names
conn = init_db('test_spec_names.db')
sy_id = insert_spec_year(conn, 999, '2026款', 3, '2026-05-18')
insert_spec_names(conn, sy_id, ['豪华型', '尊贵型', '旗舰型'])
rows = conn.execute('SELECT * FROM spec_names WHERE spec_year_id=?', (sy_id,)).fetchall()
print(rows)
conn.close()
import os; os.remove('test_spec_names.db')
"
```

- [ ] **Step 4: Commit**

```bash
git add src/db.py
git commit -m "feat: add spec_names table and insert function"
```

---

### Task 2: Update `pipeline/specs.py` to write spec_names

**Files:**
- Modify: `src/pipeline/specs.py`

- [ ] **Step 1: Pass spec_names to insert**

In `run()`, where we iterate over `config_data.items()`, capture `spec_names` and write them:

```python
# Write spec data
for year_name, (spec_names, param_rows) in config_data.items():
    sy_id = insert_spec_year(conn, sid, year_name, len(spec_names), today)
    if sy_id is None:
        continue
    params = _flatten_params(param_rows, len(spec_names))
    replace_spec_params(conn, sy_id, params)
    insert_spec_names(conn, sy_id, spec_names)  # <-- ADD THIS LINE
```

Also add the import at top:

```python
from ..db import upsert_brand, upsert_series, insert_spec_year, replace_spec_params, insert_spec_names
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from src.pipeline.specs import run; print('import OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/pipeline/specs.py
git commit -m "feat: write spec_names to database in specs pipeline"
```

---

### Task 3: Create `src/export/sales.py`

**Files:**
- Create: `src/export/__init__.py`
- Create: `src/export/sales.py`

- [ ] **Step 1: Write `src/export/__init__.py`**

```python
# export package
```

- [ ] **Step 2: Write `src/export/sales.py`**

```python
"""Export sales data from database to xlsx."""
import os
from datetime import datetime
from collections import defaultdict

from ..excel_writer import write_sales_excel

OUTPUT_DIR = os.environ.get("CARMIINE_OUTPUT", "D:/Projects/Program/carmine/output")


def run(conn, months=6, top=50, output_dir=None):
    """Export sales ranking to xlsx.

    Args:
        conn: sqlite3.Connection
        months: number of recent months (1-6)
        top: top N per sub-category
        output_dir: override output path
    """
    ts = datetime.now().strftime("%Y%m%d%H%M")
    out_dir = output_dir or os.path.join(OUTPUT_DIR, ts)
    filepath = os.path.join(out_dir, "销量排行.xlsx")
    os.makedirs(out_dir, exist_ok=True)

    # Get available months from DB
    months_list = [row[0] for row in conn.execute(
        "SELECT DISTINCT month FROM sales_monthly ORDER BY month DESC LIMIT ?",
        (months,)
    ).fetchall()]
    if not months_list:
        print("No sales data found in database.")
        return
    cutoff = months_list[-1]

    # Aggregate sales by series
    rows = conn.execute("""
        SELECT s.seriesid, s.name AS series_name, s.category,
               b.name AS brand_name, b.manufacturer,
               SUM(sm.sales) AS total_sales,
               s.price_range
        FROM sales_monthly sm
        JOIN series s ON sm.seriesid = s.seriesid
        LEFT JOIN brands b ON s.brandid = b.brandid
        WHERE sm.month >= ?
        GROUP BY s.seriesid
        ORDER BY total_sales DESC
    """, (cutoff,)).fetchall()

    # Group by main category → sub category
    from ..brands import CATEGORIES
    # Build sub→main mapping
    sub_to_main = {}
    for main, subcats in CATEGORIES.items():
        for name, _ in subcats:
            sub_to_main[name] = main

    cats = defaultdict(lambda: defaultdict(list))
    for sid, sname, cat, bname, manu, sales, price in rows:
        if not cat:
            continue
        main_cat = sub_to_main.get(cat, cat)
        cats[main_cat][cat].append({
            "车型名称": sname,
            "品牌": bname or "未知",
            "主机厂": manu or bname or "未知",
            "6个月总销量": sales,
            "价格区间": price or "",
            "子分类": cat,
        })

    # Build output structure
    output = {}
    for main_cat, sub_map in cats.items():
        output[main_cat] = []
        for sub_name, items in sub_map.items():
            items.sort(key=lambda x: x["6个月总销量"], reverse=True)
            items = items[:top]
            for i, r in enumerate(items):
                r["排名"] = i + 1
            output[main_cat].append((sub_name, items))

    write_sales_excel(output, filepath)
    print(f"Sales exported: {filepath}")
```

- [ ] **Step 3: Verify import**

```bash
uv run python -c "from src.export.sales import run; print('import OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/export/__init__.py src/export/sales.py
git commit -m "feat: add export/sales.py for sales xlsx export from database"
```

---

### Task 4: Create `src/export/specs.py`

**Files:**
- Create: `src/export/specs.py`

- [ ] **Step 1: Write `src/export/specs.py`**

```python
"""Export config specs from database to xlsx files."""
import os
import re
from datetime import datetime
from collections import defaultdict

from ..excel_writer import write_config_xlsx

OUTPUT_DIR = os.environ.get("CARMIINE_OUTPUT", "D:/Projects/Program/carmine/output")


def run(conn, output_dir=None):
    """Export all config specs to xlsx files, one per series.

    Args:
        conn: sqlite3.Connection
        output_dir: override output path
    """
    ts = datetime.now().strftime("%Y%m%d%H%M")
    out_dir = output_dir or os.path.join(OUTPUT_DIR, ts, "配置表")
    os.makedirs(out_dir, exist_ok=True)

    # Get all series with spec data, with brand/manufacturer info
    series_list = conn.execute("""
        SELECT DISTINCT sy.seriesid, s.name, s.brandid,
               b.name AS brand_name, b.manufacturer
        FROM spec_years sy
        JOIN series s ON sy.seriesid = s.seriesid
        LEFT JOIN brands b ON s.brandid = b.brandid
        ORDER BY b.manufacturer, b.name, s.name
    """).fetchall()

    stats = {"success": 0, "empty": 0}
    total = len(series_list)

    for i, (sid, sname, bid, bname, manu) in enumerate(series_list, 1):
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', sname)
        manu_name = manu or bname or "未知"
        brand_name = bname or "未知"
        dir_path = os.path.join(out_dir, manu_name, brand_name)
        filepath = os.path.join(dir_path, f"{safe_name}.xlsx")

        print(f"  [{i}/{total}] {sname}", end=" ")

        # Get all years for this series
        years = conn.execute(
            "SELECT id, year_name, spec_count FROM spec_years WHERE seriesid=? ORDER BY year_name",
            (sid,)
        ).fetchall()

        if not years:
            print("no data")
            stats["empty"] += 1
            continue

        config_data = {}
        for sy_id, year_name, spec_count in years:
            # Get spec names
            names_rows = conn.execute(
                "SELECT spec_index, spec_name FROM spec_names WHERE spec_year_id=? ORDER BY spec_index",
                (sy_id,)
            ).fetchall()
            spec_names = [row[1] for row in names_rows]
            if len(spec_names) < spec_count:
                # Fallback for old data without spec_names
                spec_names = [f"规格{i+1}" for i in range(spec_count)]

            # Get params, ordered by group → param → spec_index
            params_rows = conn.execute("""
                SELECT group_name, param_name, spec_index, value
                FROM spec_params
                WHERE spec_year_id=?
                ORDER BY group_name, param_name, spec_index
            """, (sy_id,)).fetchall()

            if not params_rows:
                continue

            # Rebuild wide matrix
            param_rows = _build_param_rows(params_rows, spec_count)
            config_data[year_name] = (spec_names, param_rows)

        if not config_data:
            print("empty params")
            stats["empty"] += 1
            continue

        os.makedirs(dir_path, exist_ok=True)
        ok = write_config_xlsx(filepath, config_data)
        if ok:
            print(f"-> {len(config_data)} years | {manu_name}/{brand_name}/{safe_name}.xlsx")
            stats["success"] += 1
        else:
            print("WRITE ERROR")

    print(f"\nDone: {stats['success']} success, {stats['empty']} empty")
    print(f"Output: {out_dir}")


def _build_param_rows(params_rows, num_specs):
    """Convert flat rows back to wide matrix format.
    
    params_rows: [(group_name, param_name, spec_index, value), ...]
    Returns: [(group_name, param_name, [values...]), ...]
    """
    groups = defaultdict(lambda: defaultdict(lambda: ["-" for _ in range(num_specs)]))
    param_order = []
    seen = set()

    for group, pname, idx, val in params_rows:
        if (group, pname) not in seen:
            seen.add((group, pname))
            param_order.append((group, pname))
        if idx < num_specs:
            groups[group][pname][idx] = val or "-"

    return [
        (group, pname, groups[group][pname])
        for group, pname in param_order
    ]
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from src.export.specs import run; print('import OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/export/specs.py
git commit -m "feat: add export/specs.py for config specs xlsx export from database"
```

---

### Task 5: Create `src/export.py` — CLI Entry Point

**Files:**
- Create: `src/export.py`

- [ ] **Step 1: Write `src/export.py`**

```python
"""CLI entry point for exporting database data to xlsx.

Usage:
    uv run python -m src.export sales  --months 6 --top 50
    uv run python -m src.export specs
    uv run python -m src.export all
"""
import argparse
import sys

from .db import init_db
from .encoding import setup
from .export.sales import run as run_sales_export
from .export.specs import run as run_specs_export


def main():
    setup()
    parser = argparse.ArgumentParser(description="Export database data to xlsx")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sales = sub.add_parser("sales", help="Export sales ranking")
    p_sales.add_argument("--months", type=int, default=6, choices=range(1, 7),
                         help="Number of recent months (1-6, default 6)")
    p_sales.add_argument("--top", type=int, default=50,
                         help="Top N per sub-category (default 50)")

    sub.add_parser("specs", help="Export all config specs as xlsx")

    sub.add_parser("all", help="Export both sales and specs (default params)")

    args = parser.parse_args()
    conn = init_db("carmine.db")

    try:
        if args.command == "sales":
            run_sales_export(conn, months=args.months, top=args.top)
        elif args.command == "specs":
            run_specs_export(conn)
        elif args.command == "all":
            run_sales_export(conn)
            run_specs_export(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI**

```bash
uv run python -m src.export --help
uv run python -m src.export sales --help
uv run python -m src.export specs --help
uv run python -m src.export all --help
```

- [ ] **Step 3: Commit**

```bash
git add src/export.py
git commit -m "feat: add export.py CLI for database-to-xlsx export"
```

---

### Task 6: Re-scrape specs to populate spec_names (then verify)

- [ ] **Step 1: Clear only spec tables and re-run specs pipeline**

```bash
cd D:/Projects/Program/carmine && uv run python -c "
from src.db import init_db
conn = init_db('carmine.db')
conn.execute('DELETE FROM spec_params')
conn.execute('DELETE FROM spec_names')
conn.execute('DELETE FROM spec_years')
conn.commit()
conn.close()
"
uv run python -m src.fetch_to_db specs --mode all
```

- [ ] **Step 2: Run export and verify output**

```bash
uv run python -m src.export all
```

Check that:
- `output/{ts}/销量排行.xlsx` exists with correct structure
- `output/{ts}/配置表/{主机厂}/{品牌}/{车型}.xlsx` files exist
- Spec names in headers match real spec names (not "规格1/规格2")

- [ ] **Step 3: Verify spec_names populated**

```bash
uv run python -c "
import sqlite3
conn = sqlite3.connect('carmine.db')
count = conn.execute('SELECT count(*) FROM spec_names').fetchone()[0]
sample = conn.execute('SELECT * FROM spec_names LIMIT 3').fetchall()
print(f'spec_names rows: {count}')
for row in sample:
    print(f'  spec_year_id={row[0]}, index={row[1]}, name={row[2]}')
conn.close()
"
```

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "test: end-to-end export verification passed"
git push
```
