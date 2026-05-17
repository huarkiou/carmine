# 经验教训

## 汽车之家品牌映射

- **品牌排行API (`subranktypeid=3`) 仅含前109个品牌**，小众品牌需通过车系详情页获取
- 车系详情 NextJS API: `/_next/data/{hash}/{seriesid}/.json` → `seriesBaseInfo.fctName` 含主机厂
- `fctName` 格式: `{主机厂}{品牌名}`，去掉末尾品牌名即得主机厂 (见 [docs/autohome-api.md](docs/autohome-api.md))
- 注意终端编码问题：GBK/UTF-8混用导致品牌名误判，始终用 hex 验证

## 主机厂命名规范

- 移除 `汽车`/`集团` 后缀: 吉利汽车→吉利, 北汽集团→北汽
- 子品牌归属母公司: 方程豹→比亚迪, 乐道→蔚来
- 例外保留: 上汽通用五菱（不改简称）；东风日产、鸿蒙智行保留原名
- 映射字典: 见 `collect.py` 的 `BRAND_TO_MANUFACTURER`

## 关键文件

| 文件 | 说明 |
|------|------|
| [collect.py](collect.py) | 主抓取脚本，含品牌-主机厂映射 |
| [docs/autohome-api.md](docs/autohome-api.md) | 汽车之家 API 文档 |
| [tools/](tools/) | 辅助脚本工具 |
