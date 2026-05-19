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
    filepath = os.path.join(out_dir, "汽车销量排行-近6个月.xlsx")
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

    # Build sub->main category mapping
    from ..brands import CATEGORIES
    sub_to_main = {}
    for main, subcats in CATEGORIES.items():
        for name, _ in subcats:
            sub_to_main[name] = main

    # Group by main category -> sub category
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
