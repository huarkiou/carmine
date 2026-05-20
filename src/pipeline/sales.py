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
                # Skip if this (levelid, month) already has data
                existing = conn.execute(
                    "SELECT 1 FROM sales_monthly WHERE levelid=? AND month=? LIMIT 1",
                    (levelid, month)
                ).fetchone()
                if existing:
                    continue

                items = fetch_series(levelid, month)
                for item in items:
                    sid_str = str(item.get("seriesid", ""))
                    sid = int(sid_str)
                    sales = int(item.get("salecount", 0) or 0)
                    bid = item.get("brandid", 0)

                    sales_rows.append((
                        sid, month, levelid, sales,
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
        upsert_series(conn, sid, bid, info["name"], info["category"], info["price"])

    if sales_rows:
        insert_sales_batch(conn, sales_rows)
        print(f"  Inserted {len(sales_rows)} sales records")

    print(f"\nDone: {len(brand_map)} brands, {len(series_info)} series, {len(sales_rows)} sales records")
