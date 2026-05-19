# 数据库存储改造设计

## 目标

将 xlsx 输出替换为 SQLite 数据库存储，支持增量更新与跨车型参数对比查询。

- 新建 `fetch_to_db.py` CLI 入口 + pipeline 管道，替代现有三个 xlsx 输出脚本
- 保留 `excel_writer.py` 供后续 tools 从数据库导出 xlsx
- 不涉及颜色渲染（spec_params 存纯文本）

## CLI

```bash
# 销量（默认最近6个月，--months 1~6）
uv run python -m src.fetch_to_db sales
uv run python -m src.fetch_to_db sales --months 3

# 配置
uv run python -m src.fetch_to_db specs              # 默认销量榜热门车系
uv run python -m src.fetch_to_db specs --mode all   # 全品牌遍历

# 全量
uv run python -m src.fetch_to_db all
uv run python -m src.fetch_to_db all --months 3
```

## 模块变更

| 模块 | 动作 | 职责 |
|------|------|------|
| `src/db.py` | 新建 | `init_db()` 建表、连接管理；`upsert_brand()`、`upsert_series()`、`insert_sales()`、`insert_spec_year()`、`replace_spec_params()` |
| `src/pipeline/__init__.py` | 新建 | 包声明 |
| `src/pipeline/sales.py` | 新建 | `run(conn, months)` — 品牌地图→分类销量→写库 |
| `src/pipeline/specs.py` | 新建 | `run(conn, mode)` — 品牌索引/销量车系列表→配置→写库 |
| `src/fetch_to_db.py` | 新建 | `argparse` 解析 CLI → 调 pipeline |
| `src/api.py` | 不变 | 复用全部 fetch 函数 |
| `src/brands.py` | 不变 | 复用品牌清洗/映射 |
| `src/excel_writer.py` | 保留 | 供后续 tools 用 |
| `src/fetch_sales.py` | **删除** | |
| `src/fetch_specs.py` | **删除** | |
| `src/fetch_specs_by_brand.py` | **删除** | |

## 数据库 Schema

数据库文件：`carmine.db`（项目根目录）

### brands — 品牌字典

```
brandid       INTEGER PRIMARY KEY
name          TEXT    NOT NULL    -- 品牌名
manufacturer  TEXT                -- 主机厂名（预清洗）
first_seen    TEXT                -- 首次抓取日期 YYYY-MM-DD
last_seen     TEXT                -- 最近抓取日期
```

### series — 车系字典

```
seriesid      INTEGER PRIMARY KEY
brandid       INTEGER NOT NULL REFERENCES brands(brandid)
name          TEXT    NOT NULL    -- 车系名
category      TEXT                -- 分类（紧凑型车/中型SUV/...）
price_range   TEXT                -- 价格区间
status        TEXT    DEFAULT '在售'   -- 在售/停售
```

### sales_monthly — 月度销量事实表

```
id            INTEGER PRIMARY KEY AUTOINCREMENT
seriesid      INTEGER NOT NULL REFERENCES series(seriesid)
month         TEXT    NOT NULL    -- YYYY-MM
sales         INTEGER NOT NULL DEFAULT 0
rank          INTEGER             -- 该分类内排名
fetched_at    TEXT    NOT NULL    -- 抓取时间戳
UNIQUE(seriesid, month)
```

增量写入：`INSERT OR IGNORE` 避免重复；若源数据变化（排名更新）则 `ON CONFLICT DO UPDATE`。

### spec_years — 配置年款元信息

```
id            INTEGER PRIMARY KEY AUTOINCREMENT
seriesid      INTEGER NOT NULL REFERENCES series(seriesid)
year_name     TEXT    NOT NULL    -- "2026款"
spec_count    INTEGER             -- 该年款规格数
fetched_at    TEXT    NOT NULL
UNIQUE(seriesid, year_name)
```

### spec_params — 配置参数明细

```
id            INTEGER PRIMARY KEY AUTOINCREMENT
spec_year_id  INTEGER NOT NULL REFERENCES spec_years(id)
group_name    TEXT                -- 参数分组（"基本参数"）
param_name    TEXT                -- 参数名（"长×宽×高"）
spec_index    INTEGER             -- 规格列索引（0-based）
value         TEXT                -- 参数值（纯文本，无颜色）
```

写入方式：先 `DELETE FROM spec_params WHERE spec_year_id = ?`，再批量 insert，以处理规格变更。

### spec_names — 规格名称

```
spec_year_id  INTEGER NOT NULL REFERENCES spec_years(id)
spec_index    INTEGER NOT NULL
spec_name     TEXT                -- "2026款 40 TFSI 豪华动感型"
PRIMARY KEY (spec_year_id, spec_index)
```

写入：`INSERT OR REPLACE`，同年款规格名变化时自动更新。

## 增量更新

- `sales_monthly`: `UNIQUE(seriesid, month)` + `ON CONFLICT DO UPDATE`，只更新排名变化的行
- `spec_years`: `UNIQUE(seriesid, year_name)` + `INSERT OR IGNORE`，已存在跳过
- `spec_params`: 先删后插，应对同年款规格增减
- `brands`/`series`: `INSERT OR REPLACE`，更新 `last_seen` 和 `status`

## db.py 接口

```python
def init_db(path="carmine.db") -> sqlite3.Connection
def upsert_brand(conn, brandid, name, manufacturer, seen_date) 
def upsert_series(conn, seriesid, brandid, name, category, price, status)
def insert_sales_batch(conn, rows: list[dict])       # 批量写入 + 冲突更新
def insert_spec_year(conn, seriesid, year_name, spec_count, fetched_at) -> spec_year_id
def replace_spec_params(conn, spec_year_id, params: list[dict])
```

批量模式：`insert_sales_batch` 一次传入多条，减少 SQLite 写入开销。

## pipeline 流程

### sales.py

```
get_months(N) → fetch_brand_map() → create_manu_map()
  → 按 CATEGORIES 遍历 levelid × month
  → 聚合 → resolve_brands()
  → upsert_brand / upsert_series / insert_sales_batch
```

### specs.py

```
mode == "all"  → fetch_brand_index() → 遍历所有车系
mode == "sales"→ fetch_brand_map() + create_manu_map() → 和 fetch_specs.py 一样
                 调 fetch_series() 按分类构建车系列表 → resolve_brands()
  → 对每车系 get_param_config → parse_config (ONLY_ON_SALE=True)
  → upsert_brand / upsert_series → insert_spec_year → replace_spec_params
```

## 查询示例（后续 tools）

```sql
-- 近6个月销量>5000的SUV
SELECT s.name, SUM(sm.sales) AS total
FROM sales_monthly sm
JOIN series s ON sm.seriesid = s.seriesid
WHERE sm.month >= '2025-12' AND s.category LIKE '%SUV%'
GROUP BY s.seriesid HAVING total > 5000
ORDER BY total DESC;

-- 所有带"座椅加热"的车型
SELECT DISTINCT s.name, p.param_name, p.value
FROM spec_params p
JOIN spec_years y ON p.spec_year_id = y.id
JOIN series s ON y.seriesid = s.seriesid
WHERE p.param_name LIKE '%座椅加热%' AND p.value != '-';

-- 轴距>2800mm的轿车（来自"长×宽×高"参数）
SELECT s.name, p.value
FROM spec_params p
JOIN spec_years y ON p.spec_year_id = y.id
JOIN series s ON y.seriesid = s.seriesid
WHERE p.param_name = '轴距' AND CAST(REPLACE(p.value, 'mm', '') AS INTEGER) > 2800
  AND s.category LIKE '%轿车%';
```
