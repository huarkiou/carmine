# 经验教训

## 数据管道

```
src/collect.py    → 调用 rank API → 动态取最新6个月 → 聚合销量 → 输出 xlsx
src/config_spec.py → 调用 config API → 遍历车系取配置表 → 按主机厂/品牌/车型输出 xlsx
```

详情见 [docs/autohome-api.md](docs/autohome-api.md)

## 品牌映射策略

1. **品牌排行API** (`subranktypeid=3`) 仅含前109个品牌 → 小众品牌缺失
2. **车系详情API** (`/_next/data/{hash}/{seriesid}/.json`) → `seriesBaseInfo.fctName` 含厂商
3. `fctName` 格式: `{主机厂}{品牌名}`，去末尾品牌名得主机厂，`_param_value()` 处理空值/颜色/子列表
4. 映射数据外置为 JSONC: [src/data/brand_manufacturer.jsonc](src/data/brand_manufacturer.jsonc)

## 终端编码陷阱

GBK/UTF-8 混用导致品牌名误判。始终用 hex 验证：`name.encode('utf-8').hex()`。
典型错误：brandid=575 hex=e59089e588a9e993b6e6b2b3 = "吉利银河"，曾被误认为"小米汽车"。

## 主机厂命名规范

- 移除 `汽车`/`集团` 后缀: 吉利汽车→吉利, 北汽集团→北汽
- 子品牌归属母公司: 方程豹/腾势/仰望→比亚迪, 乐道→蔚来
- 例外保留: 上汽通用五菱, 东风日产, 鸿蒙智行
- 映射数据: [src/data/brand_manufacturer.jsonc](src/data/brand_manufacturer.jsonc)

## 配置表数据解析

`_param_value()` 处理三种格式 (见 [src/config_spec.py](src/config_spec.py))：

| 格式 | 示例 | 处理 |
|------|------|------|
| `itemname` | `"6.88万"`, `"-"`(不适用) | 直接取值，None→"-" |
| `colorinfo.list` | 内饰颜色 `[{name:"星云灰",value:"#DAD9DF"}]` | CellRichText，每色名用自身 hex 着色 |
| `sublist` | 钥匙类型 `[{name:"遥控钥匙",value:"●"}]` | 换行拼接 `name: value` |
| 混色 | `"黑色/雪隐灰"` + `"#000000/#E7DDD5"` | 拆分后每段独立着色 |

openpyxl 回读 CellRichText 只显示纯文本属正常，颜色实际写入 XML 中（`<rPr><color rgb="FF..."/></rPr>`），Excel 打开可正常显示。

## 动态月份

`api.get_months(6)` 从排名页 filter 实时获取最新 N 个月，替代硬编码 MONTHS 列表。

## 文件写入安全

`write_config_xlsx` 使用 .tmp + 原子 rename，resume 时检测残留 .tmp 自动清理重试。

## 输出

所有脚本输出到 `output/{YYYYMMDDHHMMSSmmm}/`，`.gitignore` 已排除。

## 源码结构

```
src/
├── api.py           # API 端点、动态月份、fetch 函数
├── brands.py        # 品牌解析管道、名称清洗
├── excel_writer.py  # xlsx 输出、共享样式
├── collect.py       # 销量榜采集（编排）
├── config_spec.py   # 配置表采集（编排，含 _param_value）
└── data/
    ├── brand_manufacturer.jsonc  # 品牌→主机厂映射（含分组注释）
    └── categories.json          # 车型分类/levelid
tools/
└── verify.py        # xlsx 验证（品牌占位符、主机厂后缀）
docs/
└── autohome-api.md  # API 完整文档
```
