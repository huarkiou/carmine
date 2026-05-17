# 经验教训

## 数据管道

```
src/collect.py    → 调用 rank API → 聚合6个月销量数据 → 输出 xlsx
src/config_spec.py → 调用 config API → 遍历车系取配置表 → 按主机厂/品牌/车型输出 xlsx
```

详情见 [docs/autohome-api.md](docs/autohome-api.md)

## 品牌映射策略

1. **品牌排行API** (`subranktypeid=3`) 仅含前109个品牌 → 小众品牌缺失
2. **车系详情API** (`/_next/data/{hash}/{seriesid}/.json`) → `seriesBaseInfo.fctName` 含厂商
3. `fctName` 格式: `{主机厂}{品牌名}`，去末尾品牌名得主机厂
4. `resolve_brands()` 封装三步：fill_missing → create_manu_map → 重新应用显式映射
   见 [src/brands.py](src/brands.py)

## 终端编码陷阱

GBK/UTF-8 混用导致品牌名误判。始终用 hex 值验证：`name.encode('utf-8').hex()`。
典型错误：brandid=575 曾被误认为"小米汽车"，实际 hex=e59089e588a9e993b6e6b2b3 = "吉利银河"。

## 主机厂命名规范

- 移除 `汽车`/`集团` 后缀: 吉利汽车→吉利, 北汽集团→北汽
- 子品牌归属母公司: 方程豹/腾势/仰望→比亚迪, 乐道→蔚来
- 例外保留: 上汽通用五菱, 东风日产, 鸿蒙智行
- 完整映射: [src/brands.py](src/brands.py) 的 `BRAND_TO_MANUFACTURER` 字典

## 文件写入安全

`write_config_xlsx` 使用 .tmp + 原子 rename，防止中断产生不完整文件。
resume 时检测残留 .tmp 自动清理重试。

## 验证

`uv run python tools/verify.py <xlsx路径>` 检查品牌占位符、主机厂后缀命名规范

## 源码结构

```
src/
├── api.py           # API 端点、请求头、fetch 函数
├── brands.py        # 品牌-主机厂映射表、名称清洗、品牌解析管道
├── excel_writer.py  # xlsx 输出函数、共享样式常量
├── collect.py       # 销量榜采集（编排脚本）
└── config_spec.py   # 配置表采集（编排脚本）
tools/
└── verify.py        # 输出验证
docs/
└── autohome-api.md  # API 文档
```
