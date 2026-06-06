# carmine

采集公开汽车行业数据，生成销量排行榜与车型配置参数表。

## 功能

| 命令 | 用途 |
|------|------|
| `fetch_to_db sales` | 按车型分类采集最近 N 个月销量排行，写入数据库 |
| `fetch_to_db specs` | 采集在售车型的配置参数表，写入数据库 |
| `fetch_to_db all` | 以上两者 |
| `export sales` | 从数据库导出销量排行 xlsx |
| `export specs` | 从数据库导出配置参数表 xlsx（按主机厂/品牌/车型） |
| `export all` | 以上两者 |

采集与导出解耦：数据库支持增量更新，xlsx 按需生成。

## 环境

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) 包管理器

## 快速开始

```bash
# Windows 用户可直接双击 run.bat 进入交互菜单

uv sync

# 采集数据到数据库
uv run python -m src.fetch_to_db sales --months 6    # 最近6个月销量
uv run python -m src.fetch_to_db sales --db my.db --months 3  # 指定数据库路径
uv run python -m src.fetch_to_db specs --mode all    # 全品牌配置
uv run python -m src.fetch_to_db specs --all-years    # 含停售年款
uv run python -m src.fetch_to_db all                 # 全量（默认参数）

# 从数据库导出 xlsx
uv run python -m src.export sales --months 6 --top 50
uv run python -m src.export sales --db my.db --output reports/
uv run python -m src.export specs
uv run python -m src.export all --db data/car.db --output out/
```

## 数据库

数据存储在 `output/carmine.db`（SQLite），增量更新不重复抓取。

| 表 | 内容 |
|---|------|
| brands | 品牌字典（品牌名、主机厂） |
| series | 车系字典（名称、分类、价格区间） |
| sales_monthly | 月度销量事实表 |
| spec_years | 配置年款元信息 |
| spec_params | 配置参数明细（参数×规格矩阵） |
| spec_names | 规格列头名 |

## 输出

```
output/
├── carmine.db                    # SQLite 数据库
└── {YYYYMMDDHHmm}/
    ├── 汽车销量排行-近{months}个月.xlsx  # 分类别/品牌/主机厂/N个月汇总
    └── 配置表/
        └── {主机厂}/{品牌}/{车型}.xlsx  # 每 sheet 一个年款
```

## 配置

| 选项 | 命令 | 说明 | 默认值 |
|------|------|------|--------|
| `--all-years` | `fetch_to_db specs / all` | 含停售年款 | `False` |
| `--db` | `fetch_to_db` / `export` | 数据库文件路径 | `./output/carmine.db` |
| `--output` | `export` | xlsx 输出目录 | `./output` |
