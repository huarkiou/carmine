# 数据库导出 xlsx 设计

## 目标

新增 `export` 脚本，从 SQLite 数据库查询数据并导出为 xlsx 格式，恢复原有的输出文件结构。

## CLI

```bash
uv run python -m src.export sales  --months 6 --top 50   # 销量排行
uv run python -m src.export specs                        # 所有配置表
uv run python -m src.export all                          # 两者（默认参数）
```

`--months`：最近 N 个月（1-6，默认 6）。`--top`：每子分类取前 X 名（默认 50）。

## 模块

| 模块 | 动作 | 职责 |
|------|------|------|
| `src/export.py` | 新建 | CLI 入口，argparse 子命令分发 |
| `src/export/__init__.py` | 新建 | 包声明 |
| `src/export/sales.py` | 新建 | `run(conn, months, top)` — SQL 聚合 → `excel_writer.write_sales_excel` |
| `src/export/specs.py` | 新建 | `run(conn)` — SQL 查询重建参数矩阵 → `excel_writer.write_config_xlsx` |
| `src/excel_writer.py` | 不变 | 复用 `write_sales_excel`、`write_config_xlsx` |
| `src/db.py` | 不变 | 不直接依赖（export 自己管理连接或接受 conn） |

## 输出结构

```
output/{YYYYMMDDHHmm}/
├── 销量排行.xlsx
└── 配置表/
    └── {主机厂}/{品牌}/{车型}.xlsx
```

## 销量导出逻辑

SQL 聚合查询（联 `sales_monthly` + `series` + `brands`）：

```sql
SELECT s.seriesid, s.name AS series_name, s.category,
       b.name AS brand_name, b.manufacturer,
       SUM(sm.sales) AS total_sales,
       s.price_range
FROM sales_monthly sm
JOIN series s ON sm.seriesid = s.seriesid
JOIN brands b ON s.brandid = b.brandid
WHERE sm.month >= :cutoff_month
GROUP BY s.seriesid
ORDER BY total_sales DESC
```

应用层按 category 分组，每子分类取 top N，排序后传入 `write_sales_excel(output, filepath)`。

## 配置导出逻辑

从 `spec_years` + `spec_params` 按 seriesid 重建矩阵：

1. 查所有 `seriesid`（有 spec 数据的）
2. 对每个 seriesid，查 `spec_years` 获取年款列表
3. 对每个年款，查 `spec_params WHERE spec_year_id=?`，按 `group_name AS group, param_name AS param, spec_index AS col` 重组为宽表
4. 传入 `write_config_xlsx(filepath, config_data)`，其中 `config_data` 格式为 `{year_name: (spec_names, param_rows)}`

主机厂/品牌信息从 `brands` 表获取。

## 配置表矩阵重建

`spec_params` 存的是行式数据（每 cell 一行），导出时需要转回宽矩阵：

```python
def _build_config_data(rows, num_specs):
    """rows: [(group_name, param_name, spec_index, value), ...]"""
    groups = defaultdict(lambda: defaultdict(lambda: ["-" for _ in range(num_specs)]))
    param_order = []  # preserve insertion order
    seen = set()

    for group, pname, idx, val in rows:
        if (group, pname) not in seen:
            seen.add((group, pname))
            param_order.append((group, pname))
        groups[group][pname][idx] = val

    # Build (group_name, param_name, [values...]) rows
    param_rows = [
        (group, pname, groups[group][pname])
        for group, pname in param_order
    ]
    return param_rows
```

规格名称通过 `spec_names` 表获取：

```sql
spec_names (
    spec_year_id INTEGER REFERENCES spec_years(id),
    spec_index   INTEGER,
    spec_name    TEXT,
    PRIMARY KEY (spec_year_id, spec_index)
)
```

导出时 `spec_params JOIN spec_names ON (spec_year_id, spec_index)` 获取列头名。
