# Sales Pipeline Skip Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skip API calls for (levelid, month) pairs already present in the database, reducing incremental run time from ~30 minutes to ~5 minutes.

**Architecture:** Add `levelid` column to `sales_monthly` so each (levelid, month) can be independently checked. `pipeline/sales.py` queries DB before each API call and passes levelid through to `insert_sales_batch`.

**Tech Stack:** Python 3.10+, sqlite3.

---

### Task 1: Add `levelid` column to `sales_monthly` and update `insert_sales_batch`

**Files:**
- Modify: `src/db.py`

- [ ] **Step 1: Add `levelid` to schema**

In `SCHEMA`, change `sales_monthly` CREATE TABLE — add `levelid TEXT` after `month`:

```sql
CREATE TABLE IF NOT EXISTS sales_monthly (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    seriesid   INTEGER NOT NULL,
    month      TEXT    NOT NULL,
    levelid    TEXT    NOT NULL DEFAULT '',
    sales      INTEGER NOT NULL DEFAULT 0,
    rank       INTEGER,
    fetched_at TEXT    NOT NULL,
    UNIQUE(seriesid, month)
);
```

Since this is `CREATE TABLE IF NOT EXISTS`, existing databases won't get the new column automatically. Add a migration at the end of `init_db()`:

```python
# Migration: add levelid column if missing (v2)
try:
    conn.execute("ALTER TABLE sales_monthly ADD COLUMN levelid TEXT NOT NULL DEFAULT ''")
except sqlite3.OperationalError:
    pass  # column already exists
```

- [ ] **Step 2: Update `insert_sales_batch`**

Change docstring and SQL to accept `levelid`:

```python
def insert_sales_batch(conn, rows):
    """Batch insert/update sales. rows: list of (seriesid, month, levelid, sales, rank, fetched_at)."""
    sql = """
        INSERT INTO sales_monthly (seriesid, month, levelid, sales, rank, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(seriesid, month) DO UPDATE SET
            sales=excluded.sales,
            rank=COALESCE(excluded.rank, sales_monthly.rank),
            fetched_at=excluded.fetched_at
    """
    conn.executemany(sql, rows)
    conn.commit()
```

Note: levelid is not in the DO UPDATE clause — it's static per row, never changes.

- [ ] **Step 3: Verify**

```bash
uv run python -c "
from src.db import init_db, insert_sales_batch
conn = init_db('test_levelid.db')
insert_sales_batch(conn, [(100, '2026-04', '1', 5000, 1, '2026-05-18')])
row = conn.execute('SELECT levelid FROM sales_monthly').fetchone()
print('levelid:', row[0])
conn.close()
import os; os.remove('test_levelid.db')
"
```

- [ ] **Step 4: Commit**

```bash
git add src/db.py
git commit -m "feat: add levelid column to sales_monthly for per-category skip"
```

---

### Task 2: Update `pipeline/sales.py` — skip existing (levelid, month) and pass levelid

**Files:**
- Modify: `src/pipeline/sales.py`

- [ ] **Step 1: Add skip check before API call**

In the `for month in month_list:` loop, before calling `fetch_series(levelid, month)`, check DB:

```python
for month in month_list:
    # Skip if this (levelid, month) already has data
    existing = conn.execute(
        "SELECT 1 FROM sales_monthly WHERE levelid=? AND month=? LIMIT 1",
        (levelid, month)
    ).fetchone()
    if existing:
        continue
    items = fetch_series(levelid, month)
    ...
```

- [ ] **Step 2: Pass levelid in sales_rows tuples**

Add `levelid` to the tuple:

```python
sales_rows.append((
    sid, month, levelid, sales,
    item.get("rankNum"),
    today,
))
```

- [ ] **Step 3: Verify import**

```bash
uv run python -c "from src.pipeline.sales import run; print('import OK')"
```

- [ ] **Step 4: Commit**

```bash
git add src/pipeline/sales.py
git commit -m "perf: skip API calls for (levelid, month) already in database"
```

---

### Task 3: Verify end-to-end

- [ ] **Step 1: First run — full scrape (1 month)**

```bash
cd D:/Projects/Program/carmine && rm -f output/carmine.db && uv run python -m src.fetch_to_db sales --months 1
```

Note how many series are collected.

- [ ] **Step 2: Second run — should be instant**

```bash
uv run python -m src.fetch_to_db sales --months 1
```

Expected: "=== Step 3: Collecting 1-month sales data ===" then immediately "Done: 109 brands, 0 series, 0 sales records" — all skipped.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A && git commit -m "test: incremental skip verification passed"
```
