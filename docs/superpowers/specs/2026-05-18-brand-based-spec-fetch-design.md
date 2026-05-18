# 按品牌遍历全量采集配置表

## 目标

新增一个独立脚本 `fetch_specs_by_brand.py`，不依赖销量榜分类体系，直接从 autohome 品牌索引页获取所有品牌，遍历品牌下所有在售车系，按 `主机厂/品牌/车型.xlsx` 输出配置表。

## 流程

```
品牌索引页 → 提取所有 (brandid, brand_name)
    ↓
每个 brandid → brand 详情 API → factoryList + seriesList (含 seriesid, name, on_sale)
    ↓
筛选在售车系 → 对每 car 调 config API → parse_config() → write_config_xlsx()
    ↓
output/{YYYYMMDDHHmm}/{主机厂}/{品牌}/{车型}.xlsx
```

## 模块职责

| 模块 | 变化 |
|---|---|
| `api.py` | 新增 `fetch_brand_index()` - 抓品牌汇总页提取 brandid/名称列表 |
| `api.py` | 新增 `fetch_brand_series(brandid)` - 查品牌详情获取车系列表+主机厂 |
| `brands.py` | 不变（品牌清洗/主机厂推理可复用） |
| `excel_writer.py` | 不变（`write_config_xlsx` 复用） |
| `fetch_specs.py` | 不变（现有按分类逻辑保留） |
| `fetch_specs_by_brand.py` | **新建** - 编排上述流程 |

## 关键设计

### 品牌列表来源
- 抓取 autohome 品牌汇总页（如 `brand.html`），解析出所有品牌名和 brandid

### 在售判断
- 品牌详情 API 返回的车系列表含在售/停售标记，以此筛选

### 主机厂来源
- 优先用品牌详情 API 的 `factoryList` 中的主机厂信息
- fallback 到现有 `fctName` 推理逻辑（详情页 `seriesBaseInfo.fctName` 去品牌名）

### 去重
- 同一车系可能出现在多个品牌下（合资品牌场景），按品牌维度各自收录

### 可配置项
- `ONLY_ON_SALE = True` 在脚本顶部，控制只取在售年款 / 全部年款

## 与现有脚本的关系

- `fetch_specs.py` — 按销量分类采集（快速，覆盖主流品牌车系）
- `fetch_specs_by_brand.py` — 按品牌全量采集（完整，耗时更长，覆盖小众品牌）

两者互不依赖，共用 `api.py` / `brands.py` / `excel_writer.py`。
