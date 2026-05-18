# carmine

采集公开汽车行业数据，生成销量排行榜与车型配置参数表。

## 功能

| 脚本 | 用途 |
|------|------|
| `fetch_sales` | 按车型分类采集近6个月销量排行，输出 xlsx |
| `fetch_specs` | 采集销量靠前车型的配置参数表，按主机厂/品牌/车型存放 |
| `fetch_specs_by_brand` | 全品牌遍历采集所有在售车型配置参数表 |

## 环境

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) 包管理器

## 快速开始

```bash
uv sync
uv run python -m src.fetch_sales          # 销量榜
uv run python -m src.fetch_specs          # 热门车型配置
uv run python -m src.fetch_specs_by_brand # 全品牌配置
```

## 输出

```
output/{YYYYMMDDHHmm}/
├── 销量排行.xlsx             # 分类别/品牌/主机厂/6个月销量
└── {主机厂}/{品牌}/
    └── {车型}.xlsx           # 每个 sheet 一个年款，参数×规格矩阵
```

## 配置

| 变量 | 位置 | 说明 | 默认值 |
|------|------|------|--------|
| `ONLY_ON_SALE` | `fetch_specs.py` / `fetch_specs_by_brand.py` 顶部 | 仅采集在售年款 | `True` |
| `CATEGORY_MODE` | 环境变量 | `sales`(热门) / `all`(全部) / `跑车,皮卡`(指定) | `sales` |
| `CARMIINE_OUTPUT` | 环境变量 | 输出根目录 | `./output` |
