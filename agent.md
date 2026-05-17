# 经验教训

## 数据管道

`collect.py` → 调用三个API → 聚合6个月数据 → 输出 Excel
详情见 [docs/autohome-api.md](docs/autohome-api.md)

## 品牌映射策略

1. **品牌排行API** (`subranktypeid=3`) 仅含前109个品牌 → 小众品牌缺失
2. **车系详情API** (`/_next/data/{hash}/{seriesid}/.json`) → `seriesBaseInfo.fctName` 含厂商
3. `fctName` 格式: `{主机厂}{品牌名}`，去末尾品牌名得主机厂
4. 先运行 `create_manu_map`，再 `fill_missing_brands` 补缺失，再 `create_manu_map` 重新应用显式映射

## 终端编码陷阱

GBK/UTF-8 混用导致品牌名误判。始终用 hex 值验证：`name.encode('utf-8').hex()`。
典型错误：brandid=575 曾被误认为"小米汽车"，实际 hex=e59089e588a9e993b6e6b2b3 = "吉利银河"。

## 主机厂命名规范

- 移除 `汽车`/`集团` 后缀: 吉利汽车→吉利, 北汽集团→北汽
- 子品牌归属母公司: 方程豹/腾势/仰望→比亚迪, 乐道→蔚来
- 例外保留: 上汽通用五菱, 东风日产, 鸿蒙智行
- 完整映射见 `collect.py` 的 `BRAND_TO_MANUFACTURER` 字典

## 验证

`uv run python tools/verify.py <xlsx路径>` 检查品牌占位符、主机厂后缀命名规范

## 关键文件

| 文件 | 说明 |
|------|------|
| [collect.py](collect.py) | 销量排行榜采集，含品牌-主机厂映射 |
| [config_spec.py](config_spec.py) | 在售车型参数配置表采集 |
| [docs/autohome-api.md](docs/autohome-api.md) | 汽车之家 API 文档与参数 |
| [tools/verify.py](tools/verify.py) | xlsx 输出验证脚本 |
