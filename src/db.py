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

CREATE TABLE IF NOT EXISTS spec_names (
    spec_year_id INTEGER NOT NULL REFERENCES spec_years(id),
    spec_index   INTEGER NOT NULL,
    spec_name    TEXT,
    PRIMARY KEY (spec_year_id, spec_index)
);
"""


def init_db(path="carmine.db"):
    """Initialize database, create tables if needed, return connection."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")  # OFF allows out-of-order inserts across brands/series tables during bulk load
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
    conn.execute("BEGIN")
    conn.execute("DELETE FROM spec_params WHERE spec_year_id=?", (spec_year_id,))
    conn.executemany(
        "INSERT INTO spec_params (spec_year_id, group_name, param_name, spec_index, value) "
        "VALUES (?, ?, ?, ?, ?)",
        [(spec_year_id, g, p, i, v) for g, p, i, v in params]
    )
    conn.commit()


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
