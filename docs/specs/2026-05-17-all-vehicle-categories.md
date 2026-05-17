# 全类别车型配置表采集

## 背景

当前 CATEGORIES 仅覆盖轿车/SUV/MPV，需扩展到所有汽车之家支持的车辆类别。

## 新增类别

从 price 页 filter 提取的全部 levelid：

| 类别 | levelid | 数据源 |
|------|---------|--------|
| 跑车 | 7 | rank API (2款) |
| 微面 | 11 | rank API (5款) |
| 微卡 | 12 | price 页 API |
| 轻客 | 13 | price 页 API |
| 皮卡 | 14 | price 页 API (15款) |

注：轿车/SUV/MPV 保持从 rank API 获取（含销量数据），仅无排名数据的分类使用 price 页 API。

## 设计

### 文件重命名

`collect.py` → `fetch_sales.py`，`config_spec.py` → `fetch_specs.py`

### 变更点

1. **`src/data/all_categories.json`** — 新增，在 CATEGORIES 基础上追加跑车/微面/微卡/轻客/皮卡
2. **`src/api.py`** — 新增 `fetch_series_by_level(levelid)` 从 price 页 API 获取车系列表；移除 `fetch_all_series()`（分类逻辑上移到调用方）
3. **`src/fetch_specs.py`** — 模块级 `CATEGORY_MODE` 变量：
   - `"sales"` (默认) → 使用 CATEGORIES（销量靠前车型，行为不变）
   - `"all"` → 使用 all_categories（含跑车/皮卡等全部类别）
   - `["跑车", "皮卡"]` → 仅指定类别
4. **`src/fetch_sales.py`** — 完全不变，仅使用 CATEGORIES
5. **`docs/autohome-api.md`** — 新增 price 页 API 文档

### fetch_specs.py 使用方式

```python
# 默认：销量靠前车型配置
CATEGORY_MODE = "sales"

# 改为全部类别
CATEGORY_MODE = "all"

# 仅特定类别
CATEGORY_MODE = ["跑车", "皮卡"]
```

### fetch_sales.py 完全不受影响

仅使用 CATEGORIES（轿车/SUV/MPV），逻辑不变。

### 数据流

```
fetch_specs.py
  ├── 根据 CATEGORY_MODE 选择分类列表
  ├── 遍历子分类，调用 fetch_series(levelid) → rank API
  │   └── 有数据 → 直接使用 (含 brandid)
  └── 无数据 → fetch_series_by_level(levelid) → price 页 API
      └── 从 fctname 推断 brandid（通过 brand_map 反查）
```

### price 页 API

```
GET /_next/data/{hash}/price/levelid_{id}.json
→ pageProps.seriesList.seriesgrouplist[]
  → seriesid, seriesname, fctname (厂商名)
```

### 风险

- Price 页的 `fctname` 格式为"品牌名"或"厂商名(进口)"，需清洗后反查 brandid
- 部分小众品牌可能不在 brand_map 中 → 走 fill_missing_brands 补全
- Price 页包含停售车型 → 已被 config API 的 `conditionlist.lazyload` 自然过滤
