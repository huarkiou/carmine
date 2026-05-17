"""Verify brand-manufacturer mapping in the generated Excel file."""
import sys
from openpyxl import load_workbook

def verify(filepath):
    wb = load_workbook(filepath)
    issues = []
    stats = {"total": 0, "brands": set(), "manus": set()}

    for name in wb.sheetnames:
        ws = wb[name]
        for row in range(2, ws.max_row + 1):
            model = str(ws.cell(row=row, column=2).value or '')
            brand = str(ws.cell(row=row, column=3).value or '')
            manu = str(ws.cell(row=row, column=4).value or '')
            sales = ws.cell(row=row, column=5).value or 0

            stats["total"] += 1
            stats["brands"].add(brand)
            stats["manus"].add(manu)

            # Check for placeholder names
            if '品牌' in brand:
                issues.append(f"[BRAND] {model}: brand={brand}")
            if '品牌' in manu:
                issues.append(f"[MANU] {model}: manu={manu}")
            # Check for unwanted suffixes
            for suffix in ['汽车', '集团']:
                if manu.endswith(suffix) and manu not in ['上汽通用五菱', '东风日产', '鸿蒙智行']:
                    issues.append(f"[SUFFIX] {model}: manu={manu} ends with '{suffix}'")

    print(f"Total rows: {stats['total']}")
    print(f"Unique brands: {len(stats['brands'])}")
    print(f"Unique manufacturers: {len(stats['manus'])}")
    print(f"Issues found: {len(issues)}")
    for i in issues[:20]:
        print(f"  {i}")
    if len(issues) > 20:
        print(f"  ... and {len(issues)-20} more")

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'D:/Users/huarkiou/Downloads/汽车销量排行-近6个月.xlsx'
    verify(path)
