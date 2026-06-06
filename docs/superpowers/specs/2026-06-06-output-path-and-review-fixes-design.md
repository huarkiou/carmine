# 输出路径统一 & 审查修复 设计文档

## 范围

本设计涵盖代码审查中确定的 6 项修复：

1. 统一数据库/导出路径（移除硬编码和环境变量）
2. 根据 `--months` 动态设置导出文件名和列标题
3. "all" 模式下缺少品牌解析
4. `--all-years` CLI 标志替代 `ONLY_ON_SALE` 模块变量
5. 颜色十六进制解析失败时记录警告
6. 为 `parse_config` / `_flatten_params` 添加 pytest 测试

## 1. 统一路径处理

### 1.1 数据库路径

在 `src/db.py` 中添加一个常量：

```python
DEFAULT_DB = "output/carmine.db"
```

**标志命名约定（适用于两个入口点）：**
- `--db` — SQLite 数据库路径（采集：写入目标，导出：读取源）。默认：`output/carmine.db`
- `--output` — xlsx 输出目录（仅导出模块）。默认：`output`

`init_db()` 的默认参数保持不变，以便以编程方式使用。

**涉及的文件：**

| 文件 | 变更 |
|------|--------|
| `src/db.py` | 新增 `DEFAULT_DB = "output/carmine.db"` |
| `src/fetch_to_db.py` | 父级解析器接收 `--db`，传入 `init_db()` |
| `src/export/__main__.py` | 父级解析器接收 `--db`（输入，传入 `init_db()`）和 `--output`（xlsx 目录） |
| `src/export/sales.py` | 移除 `OUTPUT_DIR` 环境变量；`run()` 的 `output_dir` 默认值保持 `None`（函数内部使用 `is None` 检查并回退到时间戳子目录，见 1.2） |
| `src/export/specs.py` | 同上 |
| `README.md` | 更新使用示例 |

### 1.2 xlsx 输出目录和时间戳

导出函数内部使用 `output_dir is None` 检查（而非真值检查）：

```python
def run(conn, months=6, top=50, output_dir=None):
    ts = datetime.now().strftime("%Y%m%d%H%M")
    if output_dir is None:
        output_dir = os.path.join("output", ts)
    ...
```

这保留了默认时间戳子目录的行为，同时允许通过 CLI 覆盖。供应商/品牌/车系的子目录结构不变。

### 1.3 `all` 子命令标志传播

两个 `all` 子命令（采集和导出）必须显式接受并转发共享标志：

**`fetch_to_db all`：**
```python
p_all.add_argument("--months", ...)
p_all.add_argument("--db", default=db.DEFAULT_DB)
p_all.add_argument("--all-years", action="store_true")
# 调用：
run_sales(conn, months=args.months)
run_specs(conn, mode="sales", only_on_sale=not args.all_years)
```

**`export all`：**
```python
p_all.add_argument("--db", default=db.DEFAULT_DB)
p_all.add_argument("--output", default="output")
p_all.add_argument("--months", type=int, default=6, choices=range(1, 7))
p_all.add_argument("--top", type=int, default=50)
# 调用：
run_sales_export(conn, months=args.months, top=args.top, output_dir=args.output)
run_specs_export(conn, output_dir=args.output)
```

### 1.4 CLI 接口（变更后）

```bash
# 采集 — --db 设置数据库位置
uv run python -m src.fetch_to_db sales --months 6
uv run python -m src.fetch_to_db sales --db /tmp/my.db --months 3
uv run python -m src.fetch_to_db specs --mode all
uv run python -m src.fetch_to_db all --db data/car.db --all-years

# 导出 — --db 设置输入，--output 设置 xlsx 目录
uv run python -m src.export sales --months 6 --top 50
uv run python -m src.export sales --db data/car.db --output reports/
uv run python -m src.export specs --db /tmp/my.db --output out/
uv run python -m src.export all --db data/car.db --output out/
```

## 2. 动态导出文件名和列标题

`export/sales.py` 中的文件名模板和列标题均使用 `months` 参数：

```python
filepath = os.path.join(out_dir, f"汽车销量排行-近{months}个月.xlsx")

cols = ["排名", "车型名称", "品牌", "主机厂", f"{months}个月总销量", "价格区间", "子分类"]
```

在聚合和输出字典中，键由 `"6个月总销量"` 改为 `"总销量"`，以便跨月份值通用。

## 3. "all" 模式下的品牌解析

移动 `resolve_brands()` 调用，使其对 `"sales"` 和 `"all"` 模式均无条件执行。为 `"all"` 模式构建 `series_by_brand`（与 `"sales"` 模式逻辑相同 —— 从 `all_series` 字典按 `brandid` 分组）。这确保来自 `fetch_brand_index()` 的小众品牌能获得正确的名称和制造商映射。

`specs/run()` 中的具体变更：
- 在品牌写入步骤之前，将 `if mode == "sales": resolve_brands(...)` 提升为无条件调用
- 为 `"all"` 模式构建 `series_by_brand`：`for sid, info in all_series.items(): if info["brandid"]: series_by_brand[info["brandid"]].append(str(sid))`

## 4. `--all-years` CLI 标志

移除 `ONLY_ON_SALE = True` 模块级变量。在 `specs` 子命令中新增 `--all-years` 标志。

```bash
uv run python -m src.fetch_to_db specs                     # 仅限在售（默认）
uv run python -m src.fetch_to_db specs --all-years          # 所有年款
uv run python -m src.fetch_to_db all --all-years             # 传递给 specs
```

管道函数签名变更为：

```python
def run(conn, mode="sales", only_on_sale=True):
```

`parse_config()` 签名变更为：

```python
def parse_config(result, only_on_sale=True):
```

内部使用 `only_on_sale` 参数替代模块级 `ONLY_ON_SALE` 的读取。所有调用点（`specs/run()` 中）必须传入：`parse_config(result, only_on_sale)`。

## 5. 颜色解析警告

在 `_param_value()` 中，当颜色十六进制解析失败时，记录一条警告而非静默失败。有两个 try/except 块需要处理：

**分支 1（斜杠分隔的混色颜色）：**
```python
try:
    blocks.append(TextBlock(
        InlineFont(color="FF" + hp.strip() if hp.strip() else "FF000000"),
        np.strip(),
    ))
except Exception:
    print(f"  [warn] bad color value in mixed color: '{c.get('value')}'")
    blocks.append(TextBlock(InlineFont(), np.strip()))
```

**分支 2（纯色颜色）：**
```python
try:
    blocks.append(TextBlock(
        InlineFont(color="FF" + hex_color if hex_color else "FF000000"),
        name,
    ))
except Exception:
    print(f"  [warn] bad color value: '{c.get('value')}'")
    blocks.append(TextBlock(InlineFont(), name))
```

两条警告消息都使用来自 API 响应的原始 `c.get("value")`，以便于调试。

## 6. 为 `parse_config` / `_flatten_params` 添加测试

### 6.1 依赖

在 `pyproject.toml` 中添加 pytest 为 dev 依赖：

```toml
[dependency-groups]
dev = ["pytest>=8.0"]
```

用户通过 `uv sync --group dev`（开发环境）安装。普通用户无需此依赖即可运行采集/导出管道。

### 6.2 测试文件

```
tests/
├── __init__.py
├── conftest.py                 # 夹具：加载 JSON fixture 文件
├── fixtures/
│   └── config_3170.json       # 预先录制的 getParamConf 响应（奥迪A3）
└── test_pipeline_specs.py     # parse_config 和 _flatten_params 的单元测试
```

### 6.3 Fixture 形状

`config_3170.json` 包含 `get_param_config(3170)` 返回的真实响应 JSON。必须是包含 `titlelist`、`datalist`、`conditionlist` 键的字典 —— 和 API 返回的结构相同。

### 6.4 测试用例

**`parse_config`：**
| 用例 | 输入 | 预期结果 |
|--------|-------|----------|
| 正常响应（含在售年份） | 完整的 config_3170 | 2-3 个年份条目，每个包含 spec_names 和 param_rows |
| `only_on_sale=False` | 相同的 fixture | ≥ `only_on_sale=True` 时的条目数（相同或更多） |
| 空的 datalist | `{"titlelist":[], "datalist":[], "conditionlist":[]}` | 返回空字典 |
| 不含 conditionlist | `{"titlelist":[...], "datalist":[...], "conditionlist":[]}` | 返回空字典（无年份可匹配） |
| 至少有一个年份 | 输出的键 | 所有键匹配 `r"^\d{4}款$"` 格式 |

**`_flatten_params`：**
| 用例 | 输入 | 预期结果 |
|--------|-------|----------|
| 简单参数 | 1 个参数行，2 个规格 | `(num_specs)` 个输出行 |
| CellRichText 扁平化 | 带 `items` 属性的 fake 对象 | 纯文本字符串，无 `items` |
| 无值（`None`） | 值列表中的 `None` | 扁平化为 `"-"` |
| 值不足 | 值列表长度 < `num_specs` | 缺失位置填 `"-"` |

### 6.5 运行测试

```bash
uv run pytest tests/ -v
```

不依赖网络 —— fixture 文件已预录制。

## 不变更的部分

- 数据库 schema（无变更）
- 管道逻辑（除了上述品牌解析修复和 `only_on_sale` 参数传递）
- 导出文件结构和格式
- `run.bat` Windows 启动器
- `encoding.py` stdout UTF-8 设置
- `brands.py` 品牌映射逻辑
- `api.py` API 端点
