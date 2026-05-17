# 汽车之家 API 文档

## 1. 销量榜 API

用于获取车系/品牌月度销量排行数据。

**URL:** `https://www.autohome.com.cn/web-main/car/rank/getList`

**Headers 必须:**
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)
Referer: https://www.autohome.com.cn/rank/1-1-0-0_9000-x-x-x/2026-04.html
```

### 1.1 车系月销榜 (subranktypeid=1)

| 参数 | 说明 | 示例 |
|------|------|------|
| typeid | 榜单类型，销量榜固定 1 | 1 |
| subranktypeid | 子榜单：1=车系月销，2=车系周销，3=品牌月销，5=品牌周销 | 1 |
| levelid | 车型级别，逗号分隔多选 | `1`(微型车), `16,17,18,19,20`(全部SUV) |
| price | 价格区间（万），固定 `0-9000` 表示不限 | 0-9000 |
| date | 月份 | 2026-04 |
| pageindex | 页码 | 1 |
| pagesize | 每页条数 | 50 |
| from / pm / pluginversion / model / channel | 固定值 | 28 / 2 / 11.75.8 / 1 / 0 |

**返回字段 (result.list[]):**

| 字段 | 说明 |
|------|------|
| seriesname | 车系名称 |
| seriesid | 车系ID |
| brandid | 品牌ID |
| salecount | 月销量 |
| priceinfo | 价格区间（如 "6.88-8.78万"） |
| rankNum | 排名 |

**levelid 对照表:**

| 大类 | 子分类 | levelid |
|------|--------|---------|
| 轿车 | 微型车 | 1 |
| 轿车 | 小型车 | 2 |
| 轿车 | 紧凑型车 | 3 |
| 轿车 | 中型车 | 4 |
| 轿车 | 中大型车 | 5 |
| 轿车 | 大型车 | 6 |
| SUV | 小型SUV | 16 |
| SUV | 紧凑型SUV | 17 |
| SUV | 中型SUV | 18 |
| SUV | 中大型SUV | 19 |
| SUV | 大型SUV | 20 |
| MPV | 紧凑型MPV | 21 |
| MPV | 中型MPV | 22 |
| MPV | 中大型MPV | 23 |
| MPV | 大型MPV | 24 |
| 微面 | - | 11 |

### 1.2 品牌月销榜 (subranktypeid=3)

用于获取品牌ID与品牌名的映射。

额外参数：
- `entitytype=1071` (品牌实体)
- 无需 levelid

返回字段中 `seriesname` 即为品牌名称，`pvitem.argvs.brandid` 为品牌ID。

**注意：** 该接口仅返回销量前100+的品牌，小众品牌可能不在此列表中。

## 2. 车系详情 API

用于获取车系的品牌名(fctName)和制造商名(brandName)。

**URL:** `https://www.autohome.com.cn/_next/data/nextweb-prod-c_1.0.234-p_2.36.0/{seriesid}/.json`

**示例:** `https://www.autohome.com.cn/_next/data/.../3171/.json`

**返回关键字段 (pageProps.seriesBaseInfo):**

| 字段 | 说明 | 示例 |
|------|------|------|
| brandId | 品牌ID | 67 |
| brandName | 品牌名 | 斯柯达 |
| fctId | 厂商ID | 162 |
| fctName | 厂商全名 | 上汽大众斯柯达 |
| levelId | 级别ID | 4 (中型车) |
| levelName | 级别名 | 中型车 |

**fctName 解析规则：** fctName 通常格式为 `{主机厂}{品牌名}`，去掉末尾的品牌名即可得到主机厂名。如 `上汽大众斯柯达` → 去掉 `斯柯达` → `上汽大众`。

## 3. 品牌详情 API

**URL:** `https://www.autohome.com.cn/_next/data/.../price/brandid_{brandid}.json`

返回 `brandInfo.brandname` 为品牌名称，`factoryList` 为厂商列表。

## 4. 页面 NextJS 数据 API

排名页面也提供 NextJS SSR 数据：

**URL:** `https://www.autohome.com.cn/_next/data/.../rank/1-1-{levelid}-0_9000-x-x-x/{date}.html.json`

`pageProps.options.levelList` 包含完整的级别分类映射。
`pageProps.options.subranklist` 包含子榜单信息。
`pageProps.listRes.list` 包含排名数据（与 getList API 返回一致）。

## 5. 注意事项

- 所有 API 需要 `User-Agent` 和 `Referer` 头
- 响应编码为 UTF-8，但终端可能显示为 GBK 乱码，始终用 hex 验证: `str.encode('utf-8').hex()`
- 建议请求间隔 ≥ 150ms 避免限流
- NextJS build hash (`nextweb-prod-c_1.0.234-p_2.36.0`) 可能随部署更新，失效时从页面源码 `<script id="__NEXT_DATA__">` 中提取最新值
- `fctName` 去掉末尾品牌名后仍可能含 `汽车`/`集团` 后缀，需二次清洗 (见 `src/brands.py` 的 `clean_manu_name`)

## 6. 参数配置 API

用于获取车系的在售车型参数配置表。

**URL:** `https://www.autohome.com.cn/web-main/car/param/getParamConf`

| 参数 | 说明 | 示例 |
|------|------|------|
| mode | 固定 1 | 1 |
| site | 固定 1 | 1 |
| seriesid | 车系ID | 3171 |
| yearid | 可选，筛选年款 | 2025 |

**返回字段 (result):**

| 字段 | 说明 |
|------|------|
| bread | 品牌/车系元数据 (brandid, brandname, seriesid, seriesname) |
| conditionlist | 筛选条件列表：年款 (typevalue="year")、排量、变速箱等 |
| titlelist | 参数定义，按组组织 (itemtype=组名, items=参数列表) |
| datalist | 规格列表，每个规格含 specname、paramconflist (对应 titlelist 的值) |

**年款判断:** `conditionlist[0].list[]` 含所有年款，`lazyload:0`=在售。
规格的 `condition` 数组末位为年份值。

**输出脚本:** `src/config_spec.py`，开关 `ONLY_ON_SALE = True/False` 控制在售/全部年款。
输出目录: `output/{YYYYMMDDHHMMSSmmm}/` (自动创建时间戳子目录)。

参数值的 `colorinfo`（颜色）和 `sublist`（多值项如钥匙类型）在 `_param_value()` 中处理，以换行符拼接多值。
