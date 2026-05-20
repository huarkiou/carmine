# 经验教训

## 数据管道

```
src/fetch_to_db.py       → CLI 入口，子命令 sales / specs / all
src/pipeline/sales.py    → 调用 rank API → 动态取最近 N 个月 → 写入 brands/series/sales_monthly
src/pipeline/specs.py    → 调用 config API → 遍历车系取配置表 → 写入 spec_years/spec_params/spec_names
src/export/__main__.py   → CLI 入口，子命令 sales / specs / all
src/export/sales.py      → 从 DB 查询 → 聚合销量 → 输出销量排行 xlsx
src/export/specs.py      → 从 DB 查询 → 重建参数矩阵 → 输出配置表 xlsx
```

所有数据存入 SQLite (`output/carmine.db`)，支持增量更新。
导出脚本从数据库读取生成 xlsx，采集与输出解耦。

详情见 [docs/autohome-api.md](docs/autohome-api.md)。

## 数据库

6 张表（星型模型）：`brands` → `series` → `sales_monthly` / `spec_years` → `spec_params` + `spec_names`。

- `sales_monthly`: `UNIQUE(seriesid, month)`，INSERT OR IGNORE / ON CONFLICT DO UPDATE 增量更新
- `spec_years`: `UNIQUE(seriesid, year_name)`，已存在则跳过
- `spec_params`: 先 DELETE 再 INSERT，处理规格变更
- `spec_names`: `UNIQUE(spec_year_id, spec_index)`，存规格列头名

设计文档：`docs/superpowers/specs/2026-05-18-database-storage-design.md`

## 品牌映射策略

1. **品牌排行API** (`subranktypeid=3`) 仅含前109个品牌 → 小众品牌缺失
2. **车系详情API** (`/_next/data/{hash}/{seriesid}/.json`) → `seriesBaseInfo.fctName` 含厂商
3. `fctName` 格式: `{主机厂}{品牌名}`，去末尾品牌名得主机厂
4. 映射数据外置为 JSONC: [src/data/brand_manufacturer.jsonc](src/data/brand_manufacturer.jsonc)

## 编码 — 最重要

**不要手动设置 `r.encoding`。** autohome 所有页面和 API 返回的都是 UTF-8，`requests` 能自动检测。旧代码里 `r.encoding = "gb2312"` 是用错误编码解码正确数据，导致车系名全链路损坏。

```
autohome 服务器 (UTF-8) → HTTP → Python str (Unicode) → SQLite (UTF-8) → openpyxl (UTF-8)
```

全程 UTF-8，边界处不需要任何手工编码干预。

终端乱码是另一回事——Windows cmd/pwsh 默认 stdout 编码为 GBK。解决：
- pwsh profile 加 `$env:PYTHONIOENCODING = 'utf-8'`
- 项目内 `src/encoding.py` 提供 `setup()` 兜底

始终用 hex 验证：`name.encode('utf-8').hex()`。
典型错误：brandid=575 hex=e59089e588a9e993b6e6b2b3 = "吉利银河"，曾被误认为"小米汽车"。

## 主机厂命名规范

- 移除 `汽车`/`集团` 后缀: 吉利汽车→吉利, 北汽集团→北汽
- 子品牌归属母公司: 方程豹/腾势/仰望→比亚迪, 乐道→蔚来
- 例外保留: 上汽通用五菱, 东风日产, 鸿蒙智行
- 映射数据: [src/data/brand_manufacturer.jsonc](src/data/brand_manufacturer.jsonc)

## 配置表数据解析

`_param_value()` 处理三种格式 (见 `src/pipeline/specs.py`)：

| 格式 | 示例 | 处理 |
|------|------|------|
| `itemname` | `"6.88万"`, `"-"`(不适用) | 直接取值，None→"-" |
| `colorinfo.list` | 内饰颜色 `[{name:"星云灰",value:"#DAD9DF"}]` | CellRichText，每色名用自身 hex 着色 |
| `sublist` | 钥匙类型 `[{name:"遥控钥匙",value:"●"}]` | 换行拼接 `name: value` |
| 混色 | `"黑色/雪隐灰"` + `"#000000/#E7DDD5"` | 拆分后每段独立着色 |

存入数据库时，`_flatten_params()` 将 CellRichText 转为纯文本（颜色信息丢失）。

## 动态月份

`api.get_months(6)` 从排名页 filter 实时获取最新 N 个月，替代硬编码 MONTHS 列表。

## 输出

数据库: `output/carmine.db`（已 `.gitignore`）
导出 xlsx: `output/{YYYYMMDDHHmm}/`

## 源码结构

```
src/
├── api.py              # API 端点、动态月份、fetch 函数
├── brands.py           # 品牌解析管道、名称清洗
├── db.py               # SQLite schema 建表 + CRUD
├── encoding.py         # stdout UTF-8 设置
├── excel_writer.py     # xlsx 输出、共享样式
├── fetch_to_db.py      # 采集 CLI 入口
├── export/__main__.py  # 导出 CLI 入口
├── export/sales.py     # 销量导出管道
├── export/specs.py     # 配置导出管道
├── pipeline/
│   ├── __init__.py
│   ├── sales.py        # 销量采集管道
│   └── specs.py        # 配置采集管道（含 _param_value、parse_config）
└── data/
    ├── brand_manufacturer.jsonc  # 品牌→主机厂映射（含分组注释）
    ├── categories.json          # 销量分类/levelid
    └── all_categories.json      # 全类别分类（含跑车/皮卡/微卡/轻客）
tools/
└── verify.py           # xlsx 验证（品牌占位符、主机厂后缀）
docs/
├── autohome-api.md     # API 完整文档
└── superpowers/
    ├── specs/          # 设计文档
    └── plans/          # 实现计划
```
