"""Collect autohome 6-month sales data by vehicle category, output to xlsx."""
import time
import os
from datetime import datetime
from collections import defaultdict

from .api import fetch_brand_map, fetch_series, get_months
from .brands import CATEGORIES, BRAND_TO_MANUFACTURER, create_manu_map, resolve_brands
from .excel_writer import write_sales_excel

OUTPUT_DIR = "D:/Projects/Program/parse_autohome/output"


def main():
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    output_dir = os.path.join(OUTPUT_DIR, ts)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "汽车销量排行-近6个月.xlsx")
    print(f"Output: {output_path}")

    print("=== Step 1: Fetching brand list ===")
    brand_map = fetch_brand_map()

    print("=== Step 2: Building manufacturer mapping ===")
    manu_map = create_manu_map(brand_map)

    print("=== Step 3: Collecting 6-month sales data ===")
    months = get_months(6)
    all_data = {}
    series_by_brand = defaultdict(list)

    for cat_big, subcats in CATEGORIES.items():
        print(f"\n--- {cat_big} ---")
        sub_data = defaultdict(lambda: defaultdict(lambda: {
            "name": "", "brandid": 0, "total_sales": 0,
            "price": "", "months": set(),
        }))

        for sub_name, levelid in subcats:
            for month in months:
                items = fetch_series(levelid, month)
                for item in items:
                    sid = str(item.get("seriesid", ""))
                    sales = item.get("salecount", 0) or 0
                    entry = sub_data[sub_name][sid]
                    entry["name"] = item.get("seriesname", "")
                    entry["brandid"] = item.get("brandid", 0)
                    entry["total_sales"] += int(sales)
                    entry["price"] = item.get("priceinfo", "")
                    entry["months"].add(month)
                    bid = entry["brandid"]
                    if bid and sid not in series_by_brand[bid]:
                        series_by_brand[bid].append(sid)
                time.sleep(0.25)
            print(f"  {sub_name}: {len(sub_data[sub_name])} series")

        all_data[cat_big] = sub_data

    print("\n=== Step 4: Resolving brand names ===")
    resolve_brands(brand_map, manu_map, series_by_brand)

    print("\n=== Step 5: Aggregating and building output ===")
    output = {}
    unmapped = set()

    for cat_big, sub_data in all_data.items():
        output[cat_big] = []
        for sub_name, series_map in sub_data.items():
            rows = []
            for sid, info in series_map.items():
                brandid = info["brandid"]
                brand_name = brand_map.get(brandid)
                if not brand_name:
                    brand_name = f"品牌{brandid}"
                manufacturer = manu_map.get(brandid, brand_name)
                if manufacturer == brand_name and manufacturer not in BRAND_TO_MANUFACTURER:
                    unmapped.add(f"{brandid}:{brand_name}")
                rows.append({
                    "车型名称": info["name"],
                    "品牌": brand_name,
                    "主机厂": manufacturer,
                    "6个月总销量": info["total_sales"],
                    "价格区间": info["price"],
                    "子分类": sub_name,
                })
            rows.sort(key=lambda x: x["6个月总销量"], reverse=True)
            rows = rows[:50]
            for i, r in enumerate(rows):
                r["排名"] = i + 1
            output[cat_big].append((sub_name, rows))

    if unmapped:
        print(f"\nUnmapped brands (using brand name as manufacturer):")
        for u in sorted(unmapped):
            print(f"  {u}")

    print("\n=== Step 6: Writing Excel ===")
    write_sales_excel(output, output_path)
    print(f"\nDone: {output_path}")


if __name__ == "__main__":
    main()
