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
