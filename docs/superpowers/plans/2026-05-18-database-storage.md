# Database Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace xlsx-output scripts with SQLite storage, supporting incremental updates and cross-model param queries.

**Architecture:** `db.py` manages schema + CRUD. `pipeline/sales.py` collects sales, `pipeline/specs.py` collects configs — both independent, both write to `db.py`. `fetch_to_db.py` is a thin CLI dispatcher. Three old xlsx scripts deleted once pipelines verified.

**Tech Stack:** Python 3.10+, sqlite3 (stdlib), argparse (stdlib), requests, openpyxl (retained for future export tools).

---

### Task 1: Create `src/db.py` — Database Schema and CRUD

**Files:**
- Create: `src/db.py`

- [ ] **Step 1: Write `src/db.py`**

```python
"""SQLite database schema, connection management, and CRUD operations."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS brands (
    brandid      INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    manufacturer TEXT,
    first_seen   TEXT,
    last_seen    TEXT
);

CREATE TABLE IF NOT EXISTS series (
    seriesid    INTEGER PRIMARY KEY,
    brandid     INTEGER NOT NULL DEFAULT 0,
    name        TEXT    NOT NULL,
    category    TEXT,
    price_range TEXT,
    status      TEXT    DEFAULT '在售'
);

CREATE TABLE IF NOT EXISTS sales_monthly (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    seriesid   INTEGER NOT NULL,
    month      TEXT    NOT NULL,
    sales      INTEGER NOT NULL DEFAULT 0,
    rank       INTEGER,
    fetched_at TEXT    NOT NULL,
    UNIQUE(seriesid, month)
);

CREATE TABLE IF NOT EXISTS spec_years (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    seriesid    INTEGER NOT NULL,
    year_name   TEXT    NOT NULL,
    spec_count  INTEGER,
    fetched_at  TEXT    NOT NULL,
    UNIQUE(seriesid, year_name)
);

CREATE TABLE IF NOT EXISTS spec_params (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_year_id INTEGER NOT NULL REFERENCES spec_years(id),
    group_name   TEXT,
    param_name   TEXT,
    spec_index   INTEGER,
    value        TEXT
);
"""


def init_db(path="carmine.db"):
    """Initialize database, create tables if needed, return connection."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")  # deferred enforcement for insertion order
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_brand(conn, brandid, name, manufacturer, seen_date):
    """Insert or update a brand record."""
    conn.execute("""
        INSERT INTO brands (brandid, name, manufacturer, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(brandid) DO UPDATE SET
            name=COALESCE(NULLIF(excluded.name,''), brands.name),
            manufacturer=COALESCE(NULLIF(excluded.manufacturer,''), brands.manufacturer),
            last_seen=excluded.last_seen
    """, (brandid, name, manufacturer, seen_date, seen_date))
    conn.commit()


def upsert_series(conn, seriesid, brandid, name, category="", price_range="", status="在售"):
    """Insert or update a series record without wiping existing non-empty fields."""
    conn.execute("""
        INSERT INTO series (seriesid, brandid, name, category, price_range, status)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(seriesid) DO UPDATE SET
            brandid=IIF(excluded.brandid!=0, excluded.brandid, series.brandid),
            name=COALESCE(NULLIF(excluded.name,''), series.name),
            category=COALESCE(NULLIF(excluded.category,''), series.category),
            price_range=COALESCE(NULLIF(excluded.price_range,''), series.price_range),
            status=excluded.status
    """, (seriesid, brandid or 0, name, category, price_range, status))
    conn.commit()


def insert_sales_batch(conn, rows):
    """Batch insert/update sales. rows: list of (seriesid, month, sales, rank, fetched_at)."""
    sql = """
        INSERT INTO sales_monthly (seriesid, month, sales, rank, fetched_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(seriesid, month) DO UPDATE SET
            sales=excluded.sales,
            rank=COALESCE(excluded.rank, sales_monthly.rank),
            fetched_at=excluded.fetched_at
    """
    conn.executemany(sql, rows)
    conn.commit()


def insert_spec_year(conn, seriesid, year_name, spec_count, fetched_at):
    """Insert a spec year (or ignore if exists). Return id."""
    conn.execute("""
        INSERT OR IGNORE INTO spec_years (seriesid, year_name, spec_count, fetched_at)
        VALUES (?, ?, ?, ?)
    """, (seriesid, year_name, spec_count, fetched_at))
    conn.commit()
    row = conn.execute(
        "SELECT id FROM spec_years WHERE seriesid=? AND year_name=?",
        (seriesid, year_name)
    ).fetchone()
    return row[0] if row else None


def replace_spec_params(conn, spec_year_id, params):
    """Delete old params for spec_year_id and insert new ones.
    params: list of (group_name, param_name, spec_index, value)
    """
    conn.execute("DELETE FROM spec_params WHERE spec_year_id=?", (spec_year_id,))
    conn.executemany(
        "INSERT INTO spec_params (spec_year_id, group_name, param_name, spec_index, value) "
        "VALUES (?, ?, ?, ?, ?)",
        [(spec_year_id, g, p, i, v) for g, p, i, v in params]
    )
    conn.commit()
```

- [ ] **Step 2: Verify CRUD**

```bash
uv run python -c "
from src.db import init_db, upsert_brand, upsert_series, insert_sales_batch, insert_spec_year, replace_spec_params
conn = init_db('test_carmine.db')
upsert_brand(conn, 1, 'TestBrand', 'TestManu', '2026-05-18')
upsert_series(conn, 100, 1, 'TestSeries', 'SUV', '10-15万')
insert_sales_batch(conn, [(100, '2026-04', 5000, 1, '2026-05-18')])
sy_id = insert_spec_year(conn, 100, '2026款', 3, '2026-05-18')
replace_spec_params(conn, sy_id, [('基本参数', '轴距', 0, '2700mm')])
for t in ['brands','series','sales_monthly','spec_years','spec_params']:
    print(f'{t}:', conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0])
conn.close(); import os; os.remove('test_carmine.db'); print('OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add src/db.py
git commit -m "feat: add db.py with schema, CRUD, and batch operations"
```

---

### Task 2: Create `src/pipeline/sales.py` — Sales Pipeline

**Files:**
- Create: `src/pipeline/__init__.py`
- Create: `src/pipeline/sales.py`

- [ ] **Step 1: Write `src/pipeline/__init__.py`**

```python
# pipeline package
```

- [ ] **Step 2: Write `src/pipeline/sales.py`**

```python
"""Sales data collection pipeline — fetches rankings and writes to database."""
import time
from datetime import datetime
from collections import defaultdict

from ..api import fetch_brand_map, fetch_series, get_months
from ..brands import CATEGORIES, create_manu_map, resolve_brands
from ..db import upsert_brand, upsert_series, insert_sales_batch


def run(conn, months=6):
    """Collect sales data for the latest N months, write to database.

    Args:
        conn: sqlite3.Connection from db.init_db()
        months: N (1-6), number of recent months to fetch
    """
    today = datetime.now().strftime("%Y-%m-%d")
    months = min(months, 6)

    print("=== Step 1: Fetching brand list ===")
    brand_map = fetch_brand_map()

    print("=== Step 2: Building manufacturer mapping ===")
    manu_map = create_manu_map(brand_map)

    print(f"=== Step 3: Collecting {months}-month sales data ===")
    month_list = get_months(months)
    series_by_brand = defaultdict(list)
    sales_rows = []
    series_info = {}  # seriesid -> {name, brandid, category, price}

    for cat_big, subcats in CATEGORIES.items():
        print(f"\n--- {cat_big} ---")
        for sub_name, levelid in subcats:
            count = 0
            for month in month_list:
                items = fetch_series(levelid, month)
                for item in items:
                    sid_str = str(item.get("seriesid", ""))
                    sid = int(sid_str)
                    sales = int(item.get("salecount", 0) or 0)
                    bid = item.get("brandid", 0)

                    sales_rows.append((
                        sid, month, sales,
                        item.get("rankNum"),
                        today,
                    ))

                    if sid not in series_info:
                        series_info[sid] = {
                            "name": item.get("seriesname", ""),
                            "brandid": bid,
                            "category": sub_name,
                            "price": item.get("priceinfo", ""),
                        }
                    if bid and sid_str not in series_by_brand[bid]:
                        series_by_brand[bid].append(sid_str)
                    count += 1
                time.sleep(0.25)
            print(f"  {sub_name}: {count} rows")

    print("\n=== Step 4: Resolving brand names ===")
    resolve_brands(brand_map, manu_map, series_by_brand)

    print("=== Step 5: Writing to database ===")
    for brandid, brand_name in brand_map.items():
        manu = manu_map.get(brandid, brand_name)
        upsert_brand(conn, brandid, brand_name, manu, today)

    for sid, info in series_info.items():
        bid = info["brandid"]
        brand_name = brand_map.get(bid, "")
        if not brand_name:
            brand_name = info.get("name", "")
        upsert_series(conn, sid, bid, info["name"], info["category"], info["price"])

    if sales_rows:
        insert_sales_batch(conn, sales_rows)
        print(f"  Inserted {len(sales_rows)} sales records")

    print(f"\nDone: {len(brand_map)} brands, {len(series_info)} series, {len(sales_rows)} sales records")
```

- [ ] **Step 3: Verify import works**

```bash
uv run python -c "from src.pipeline.sales import run; print('import OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/pipeline/__init__.py src/pipeline/sales.py
git commit -m "feat: add pipeline/sales.py for sales data collection to db"
```

---

### Task 3: Create `src/pipeline/specs.py` — Specs Pipeline

**Files:**
- Create: `src/pipeline/specs.py`

- [ ] **Step 1: Write `src/pipeline/specs.py`**

```python
"""Specs data collection pipeline — fetches config tables and writes to database."""
import time
import re
import os
from datetime import datetime
from collections import defaultdict

from ..api import (
    fetch_brand_map, fetch_brand_index, fetch_series, fetch_series_by_level,
    get_param_config, get_latest_month,
)
from ..brands import CATEGORIES, clean_manu_name, create_manu_map, resolve_brands
from ..db import upsert_brand, upsert_series, insert_spec_year, replace_spec_params

ONLY_ON_SALE = True


def run(conn, mode="sales"):
    """Collect config specs and write to database.

    Args:
        conn: sqlite3.Connection
        mode: "sales" (default, hot-selling series) or "all" (all brands)
    """
    today = datetime.now().strftime("%Y-%m-%d")

    print("=== Step 1: Fetching brand index ===")
    if mode == "all":
        brand_map = fetch_brand_map()
        manu_map = create_manu_map(brand_map)
    else:
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

        # Check if this series+year already exists in DB
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

        config_data, _ = _parse_config(result)
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


def _parse_config(result):
    """Reuse parse_config from fetch_specs (will be deleted later, so import inline)."""
    from ..fetch_specs import parse_config
    return parse_config(result)


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
```

- [ ] **Step 2: Verify import works**

```bash
uv run python -c "from src.pipeline.specs import run; print('import OK')"
```

- [ ] **Step 3: Commit**

```bash
git add src/pipeline/specs.py
git commit -m "feat: add pipeline/specs.py for config spec collection to db"
```

---

### Task 4: Create `src/fetch_to_db.py` — CLI Entry Point

**Files:**
- Create: `src/fetch_to_db.py`

- [ ] **Step 1: Write `src/fetch_to_db.py`**

```python
"""CLI entry point for database-based data collection.

Usage:
    uv run python -m src.fetch_to_db sales [--months N]
    uv run python -m src.fetch_to_db specs [--mode {sales|all}]
    uv run python -m src.fetch_to_db all   [--months N]
"""
import argparse
import sys

from .db import init_db
from .pipeline.sales import run as run_sales
from .pipeline.specs import run as run_specs


def main():
    parser = argparse.ArgumentParser(description="Collect automotive data into SQLite database")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sales = sub.add_parser("sales", help="Collect monthly sales rankings")
    p_sales.add_argument("--months", type=int, default=6, choices=range(1, 7),
                         help="Number of recent months (1-6, default 6)")

    p_specs = sub.add_parser("specs", help="Collect config specs")
    p_specs.add_argument("--mode", choices=["sales", "all"], default="sales",
                         help="sales=hot-selling series, all=all brands (default sales)")

    p_all = sub.add_parser("all", help="Collect both sales and specs")
    p_all.add_argument("--months", type=int, default=6, choices=range(1, 7),
                       help="Number of recent months for sales (1-6, default 6)")

    args = parser.parse_args()
    conn = init_db("carmine.db")

    try:
        if args.command == "sales":
            run_sales(conn, months=args.months)
        elif args.command == "specs":
            run_specs(conn, mode=args.mode)
        elif args.command == "all":
            run_sales(conn, months=args.months)
            run_specs(conn, mode="sales")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI parses correctly**

```bash
uv run python -m src.fetch_to_db --help
uv run python -m src.fetch_to_db sales --help
uv run python -m src.fetch_to_db specs --help
uv run python -m src.fetch_to_db all --help
```

- [ ] **Step 3: Commit**

```bash
git add src/fetch_to_db.py
git commit -m "feat: add fetch_to_db.py CLI entry point"
```

---

### Task 5: Delete Old Scripts

**Files:**
- Delete: `src/fetch_sales.py`
- Delete: `src/fetch_specs.py`
- Delete: `src/fetch_specs_by_brand.py`

- [ ] **Step 1: Remove old scripts**

```bash
rm src/fetch_sales.py src/fetch_specs.py src/fetch_specs_by_brand.py
```

- [ ] **Step 2: Verify imports still work (no stale references)**

```bash
uv run python -c "from src.pipeline.sales import run; from src.pipeline.specs import run; from src.fetch_to_db import main; print('OK')"
```

Wait — `pipeline/specs.py` imports `parse_config` from `..fetch_specs`. After deleting `fetch_specs.py`, this will break! Need to inline `parse_config` and `_param_value` into `specs.py` or a shared module.

- [ ] **Step 3: Inline `parse_config` and `_param_value` into `pipeline/specs.py`**

Read the current `src/fetch_specs.py`, extract `parse_config`, `_param_value`, and all imports (`from openpyxl.cell.rich_text import ...`), inline them into `pipeline/specs.py` before the `_parse_config` wrapper. Then delete the old wrapper and the old files.

```python
# After inlining, pipeline/specs.py starts with:
import time
import re
from datetime import datetime
from collections import defaultdict

from openpyxl.cell.rich_text import TextBlock, CellRichText
from openpyxl.cell.text import InlineFont

# ... (current imports)
# ... (_param_value, parse_config, _flatten_params, run)
```

The `_parse_config` wrapper can be removed after inlining — just call `parse_config(result)` directly in `run()`.

- [ ] **Step 4: Verify**

```bash
uv run python -c "from src.pipeline.specs import run, parse_config, _param_value; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old xlsx scripts, inline parse_config into pipeline/specs.py"
```

---

### Task 6: End-to-End Verification

- [ ] **Step 1: Run sales pipeline (1 month, fast)**

```bash
rm -f carmine.db && uv run python -m src.fetch_to_db sales --months 1
```

Expected: prints brand count, series count, sales row count. `carmine.db` created.

- [ ] **Step 2: Run sales again (verify idempotent)**

```bash
uv run python -m src.fetch_to_db sales --months 1
```

Expected: same counts, no errors.

- [ ] **Step 3: Run specs pipeline (sales mode, limit test)**

Test a single series to avoid long run. Temporarily add `break` or run a quick Python snippet:

```bash
uv run python -c "
from src.db import init_db
from src.api import get_param_config
from src.pipeline.specs import parse_config, _flatten_params
from src.db import upsert_series, insert_spec_year, replace_spec_params

conn = init_db('carmine.db')
result = get_param_config('3170')  # Audi A3
config_data, _ = parse_config(result)
upsert_series(conn, 3170, 33, '奥迪A3', '紧凑型车', '', '在售')
for year_name, (spec_names, param_rows) in config_data.items():
    sy_id = insert_spec_year(conn, 3170, year_name, len(spec_names), '2026-05-18')
    params = _flatten_params(param_rows, len(spec_names))
    replace_spec_params(conn, sy_id, params)
    print(f'{year_name}: {len(spec_names)} specs, {len(params)} param cells')

# Verify query
for t in ['brands','series','sales_monthly','spec_years','spec_params']:
    print(f'{t}:', conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0])
conn.close()
"
```

Expected: 2026款/2025款 specs visible, param counts matching.

- [ ] **Step 4: Query test**

```bash
uv run python -c "
import sqlite3
conn = sqlite3.connect('carmine.db')
# Top 5 series by sales
for row in conn.execute('''
    SELECT s.name, sm.month, sm.sales
    FROM sales_monthly sm JOIN series s ON sm.seriesid = s.seriesid
    ORDER BY sm.sales DESC LIMIT 5
'''):
    print(row)
# Param query
for row in conn.execute('''
    SELECT s.name, p.group_name, p.param_name, p.value
    FROM spec_params p
    JOIN spec_years y ON p.spec_year_id = y.id
    JOIN series s ON y.seriesid = s.seriesid
    WHERE p.param_name LIKE '%长%宽%高%'
    LIMIT 3
'''):
    print(row)
conn.close()
"
```

- [ ] **Step 5: Commit any fixes and push**

```bash
git add -A && git commit -m "test: end-to-end verification passed"
git push
```
