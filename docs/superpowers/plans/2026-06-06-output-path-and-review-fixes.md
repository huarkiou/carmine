# 输出路径统一 & 审查修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一 CLI 输出/数据库路径、修复品牌解析、添加 --all-years 标志、为关键管道函数添加测试。

**Architecture:** 6 项修复，分布在 12 个任务中，按依赖关系排列。基础变更优先（常量、参数），然后进行管道修复，最后进行 CLI 和测试更新。每个任务都自包含且可独立验证。

**Tech Stack:** Python 3.10+, sqlite3, argparse, openpyxl, requests, json5, pytest (dev dependency)

---

## 文件结构

| 文件 | 角色 | 操作 |
|------|-------|--------|
| `src/db.py` | SQLite schema, CRUD, DEFAULT_DB 常量 | 修改：添加常量 |
| `src/pipeline/specs.py` | 配置规格采集管道 | 修改：移除 ONLY_ON_SALE，添加 only_on_sale 参数，修复 all 模式品牌解析，添加颜色警告 |
| `src/fetch_to_db.py` | 采集 CLI 入口点 | 修改：添加 --db，为 all 子命令传播 --all-years |
| `src/export/__main__.py` | 导出 CLI 入口点 | 修改：添加 --db 和 --output，为 all 子命令传播标志 |
| `src/export/sales.py` | 销量导出管道 | 修改：移除 OUTPUT_DIR 环境变量，None 检查，动态文件名/标题 |
| `src/export/specs.py` | 规格导出管道 | 修改：移除 OUTPUT_DIR 环境变量，None 检查 |
| `pyproject.toml` | 项目元数据 | 修改：添加 dev 依赖组 |
| `tests/` | 测试目录 | 创建：conftest、fixture、测试文件 |
| `README.md` | 用户文档 | 修改：CLI 使用示例 |

---

### 任务 1：添加 DEFAULT_DB 到 db.py

**文件：**
- 修改：`src/db.py:59-61`

- [ ] **第 1 步：在 init_db 上方添加常量**

在第 59 行（`def init_db` 之前）插入：

```python
DEFAULT_DB = "output/carmine.db"
```

- [ ] **第 2 步：验证导入**

```bash
uv run python -c "from src.db import DEFAULT_DB, init_db; print(DEFAULT_DB)"
```

预期：`output/carmine.db`

- [ ] **第 3 步：提交**

```bash
git add src/db.py
git commit -m "feat: add DEFAULT_DB constant to db.py"
```

---

### 任务 2：添加 pytest 为 dev 依赖

**文件：**
- 修改：`pyproject.toml`

- [ ] **第 1 步：在 [project] 块之后添加 [dependency-groups]**

读取当前 `pyproject.toml`。在最后一行之后追加：

```toml
[dependency-groups]
dev = ["pytest>=8.0"]
```

- [ ] **第 2 步：安装 dev 依赖**

```bash
uv sync --group dev
```

- [ ] **第 3 步：验证 pytest 可用**

```bash
uv run pytest --version
```

预期：pytest 8.x.x

- [ ] **第 4 步：提交**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add pytest as dev dependency"
```

---

### 任务 3：捕获 config_3170.json fixture

**文件：**
- 创建：`tests/__init__.py`
- 创建：`tests/fixtures/config_3170.json`

- [ ] **第 1 步：创建 tests 目录并初始化**

```bash
mkdir -p tests/fixtures
touch tests/__init__.py
```

- [ ] **第 2 步：捕获 API 响应**

```bash
uv run python -c "
import json, os
from src.api import get_param_config
os.makedirs('tests/fixtures', exist_ok=True)
result = get_param_config(3170)
with open('tests/fixtures/config_3170.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f'Captured: {len(json.dumps(result))} bytes')
"
```

预期：`Captured: ... bytes`

- [ ] **第 3 步：验证 fixture 文件存在且有效**

```bash
uv run python -c "import json; d=json.load(open('tests/fixtures/config_3170.json')); print('titlelist:', len(d.get('titlelist',[])), 'datalist:', len(d.get('datalist',[])), 'conditionlist:', len(d.get('conditionlist',[])))"
```

预期：titlelist: N, datalist: M, conditionlist: K（数字 > 0）

- [ ] **第 4 步：提交**

```bash
git add tests/__init__.py tests/fixtures/config_3170.json
git commit -m "test: capture config_3170.json fixture from API"
```

---

### 任务 4：为 parse_config 和 _flatten_params 编写测试

**文件：**
- 创建：`tests/conftest.py`
- 创建：`tests/test_pipeline_specs.py`

- [ ] **第 1 步：编写 conftest.py（fixture 加载器）**

```python
"""Test fixtures for pipeline/specs tests."""
import json
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def config_3170():
    """Pre-captured getParamConf response for series 3170 (Audi A3)."""
    with open(FIXTURES / "config_3170.json", "r", encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **第 2 步：编写 test_pipeline_specs.py**

```python
"""Tests for parse_config and _flatten_params."""
from src.pipeline.specs import parse_config, _flatten_params


class TestParseConfig:
    def test_returns_years_for_valid_response(self, config_3170):
        result, _ = parse_config(config_3170)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_keys_match_year_pattern(self, config_3170):
        result, _ = parse_config(config_3170)
        for key in result:
            assert key.endswith("款"), f"Key '{key}' should end with '款'"

    def test_each_entry_has_spec_names_and_param_rows(self, config_3170):
        result, _ = parse_config(config_3170)
        for year_name, (spec_names, param_rows) in result.items():
            assert isinstance(spec_names, list)
            assert isinstance(param_rows, list)
            assert len(spec_names) > 0

    def test_empty_response_returns_empty_dict(self):
        empty = {"titlelist": [], "datalist": [], "conditionlist": []}
        result, _ = parse_config(empty)
        assert result == {}

    def test_no_conditionlist_returns_empty_dict(self):
        no_cond = {"titlelist": [{"itemtype": "基本参数", "items": []}], "datalist": [], "conditionlist": []}
        result, _ = parse_config(no_cond)
        assert result == {}


class TestFlattenParams:
    def test_simple_params(self):
        param_rows = [("基本参数", "轴距", ["2700mm", "2680mm"])]
        result = _flatten_params(param_rows, 2)
        assert len(result) == 2
        assert result[0] == ("基本参数", "轴距", 0, "2700mm")
        assert result[1] == ("基本参数", "轴距", 1, "2680mm")

    def test_none_value_becomes_dash(self):
        param_rows = [("基本参数", "轴距", [None])]
        result = _flatten_params(param_rows, 1)
        assert result[0][3] == "-"

    def test_fewer_values_than_specs_pads_with_dash(self):
        param_rows = [("基本参数", "轴距", ["2700mm"])]
        result = _flatten_params(param_rows, 3)
        assert len(result) == 3
        assert result[1][3] == "-"
        assert result[2][3] == "-"

    def test_cell_rich_text_flattened(self):
        class FakeText:
            def __init__(self, text):
                self.text = text
        class FakeRichText:
            def __init__(self, texts):
                self.items = texts
        rt = FakeRichText([FakeText("红色"), FakeText("/"), FakeText("蓝色")])
        param_rows = [("车身", "外观颜色", [rt])]
        result = _flatten_params(param_rows, 1)
        assert result[0][3] == "红色/蓝色"
```

- [ ] **第 3 步：运行测试 —— 预期 9 个通过（only_on_sale 测试在任务 5 中添加）**

```bash
uv run pytest tests/test_pipeline_specs.py -v
```

预期：9 passed

- [ ] **第 4 步：提交**

```bash
git add tests/conftest.py tests/test_pipeline_specs.py
git commit -m "test: add unit tests for parse_config and _flatten_params"
```

---

### 任务 5：移除 ONLY_ON_SALE 模块变量，添加 only_on_sale 参数

**文件：**
- 修改：`src/pipeline/specs.py:27,30,107,226,236`

**文件：**
- 修改：`src/pipeline/specs.py:27,30,107,226,236`
- 修改：`tests/test_pipeline_specs.py`（添加 only_on_sale 测试用例）

- [ ] **第 1 步：运行现有测试以确认基线**

```bash
uv run pytest tests/test_pipeline_specs.py -v
```

预期：9 passed

- [ ] **第 2 步：修改 parse_config 签名（第 226 行）**

将：
```python
def parse_config(result):
```
替换为：
```python
def parse_config(result, only_on_sale=True):
```

- [ ] **第 3 步：更新 parse_config 第 236 行以使用参数**

将：
```python
                if not ONLY_ON_SALE or y.get("lazyload") == 0:
```
替换为：
```python
                if not only_on_sale or y.get("lazyload") == 0:
```

- [ ] **第 4 步：修改 run() 签名（第 30 行）**

将：
```python
def run(conn, mode="sales"):
```
替换为：
```python
def run(conn, mode="sales", only_on_sale=True):
```

- [ ] **第 5 步：更新 run() 中对 parse_config 的调用（第 107 行）**

将：
```python
        config_data, _ = parse_config(result)
```
替换为：
```python
        config_data, _ = parse_config(result, only_on_sale)
```

- [ ] **第 6 步：移除模块级 ONLY_ON_SALE（第 27 行）**

删除这一行：
```python
ONLY_ON_SALE = True
```

- [ ] **第 7 步：更新 run() 的状态消息（第 107 行之后的消息）**

第 107 行的消息：
```python
            print("no on-sale data" if ONLY_ON_SALE else "empty")
```
替换为：
```python
            print("no on-sale data" if only_on_sale else "empty")
```

- [ ] **第 8 步：添加 only_on_sale 过滤行为的测试用例**

在 `tests/test_pipeline_specs.py` 中，位于 `test_no_conditionlist_returns_empty_dict` 之后、`class TestFlattenParams` 之前，插入：

```python
    def test_only_on_sale_filters_years(self, config_3170):
        result_on_sale, _ = parse_config(config_3170, only_on_sale=True)
        result_all, _ = parse_config(config_3170, only_on_sale=False)
        assert len(result_all) >= len(result_on_sale)
```

- [ ] **第 9 步：运行测试**

```bash
uv run pytest tests/test_pipeline_specs.py -v
```

预期：10 passed

- [ ] **第 10 步：提交**

```bash
git add src/pipeline/specs.py
git commit -m "refactor: replace ONLY_ON_SALE module-level var with only_on_sale parameter"
```

---

### 任务 6：修复 "all" 模式下的品牌解析

**文件：**
- 修改：`src/pipeline/specs.py:62-68`

- [ ] **第 1 步：为 all 模式构建 series_by_brand 并提升 resolve_brands 调用**

当前 `run()` 在 `if mode == "sales":` 块内（约第 62 行）有品牌解析。需要将其移出该条件，并同时也为 `"all"` 模式构建 `series_by_brand`。

读取 `src/pipeline/specs.py` 第 62-68 行附近的当前代码。将：
```python
    # Resolve brands for "sales" mode
    if mode == "sales":
        series_by_brand = defaultdict(list)
        for sid, info in all_series.items():
            bid = info["brandid"]
            if bid:
                series_by_brand[bid].append(str(sid))
        resolve_brands(brand_map, manu_map, series_by_brand)
```
替换为：
```python
    # Resolve brands for all modes
    series_by_brand = defaultdict(list)
    for sid, info in all_series.items():
        bid = info["brandid"]
        if bid:
            series_by_brand[bid].append(str(sid))
    resolve_brands(brand_map, manu_map, series_by_brand)
```

- [ ] **第 2 步：验证导入**

```bash
uv run python -c "from src.pipeline.specs import run; print('import OK')"
```

- [ ] **第 3 步：运行测试**

```bash
uv run pytest tests/test_pipeline_specs.py -v
```

预期：10 passed

- [ ] **第 4 步：提交**

```bash
git add src/pipeline/specs.py
git commit -m "fix: resolve brands for all mode, not just sales mode"
```

---

### 任务 7：添加颜色解析失败时的警告

**文件：**
- 修改：`src/pipeline/specs.py:198-212`（`_param_value` 函数中的两个 try/except 块）

- [ ] **第 1 步：为斜杠分隔颜色分支添加警告**

找到第一个 `except Exception:` 块（斜杠分隔分支，约第 198 行）。将：
```python
                    except Exception:
                        blocks.append(TextBlock(InlineFont(), np.strip()))
```
替换为：
```python
                    except Exception:
                        print(f"  [warn] bad color value in mixed color: '{c.get('value')}'")
                        blocks.append(TextBlock(InlineFont(), np.strip()))
```

- [ ] **第 2 步：为纯色分支添加警告**

找到第二个 `except Exception:` 块（纯色分支，约第 212 行）。将：
```python
                except Exception:
                    blocks.append(TextBlock(InlineFont(), name))
```
替换为：
```python
                except Exception:
                    print(f"  [warn] bad color value: '{c.get('value')}'")
                    blocks.append(TextBlock(InlineFont(), name))
```

- [ ] **第 3 步：验证**

```bash
uv run python -c "from src.pipeline.specs import _param_value; print('import OK')"
```

- [ ] **第 4 步：运行测试**

```bash
uv run pytest tests/test_pipeline_specs.py -v
```

预期：10 passed

- [ ] **第 5 步：提交**

```bash
git add src/pipeline/specs.py
git commit -m "fix: log warnings on color hex parse failure instead of silent fallback"
```

---

### 任务 8：更新 fetch_to_db.py CLI —— --db 和 --all-years

**文件：**
- 修改：`src/fetch_to_db.py:11,18-51`

- [ ] **第 1 步：从 db 导入 DEFAULT_DB**

在第 11 行之后（`from .db import init_db`），添加 DEFAULT_DB 到导入：

```python
from .db import init_db, DEFAULT_DB
```

- [ ] **第 2 步：为 sales 子命令添加 --db，为 specs 添加 --all-years**

当前 parser 设置在约第 18-50 行。用以下内容替换整个 parser 定义块（从 `parser = argparse.ArgumentParser(...)` 到 `args = parser.parse_args()`）：

```python
def main():
    setup()
    parser = argparse.ArgumentParser(
        description="Collect automotive data into SQLite database"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_sales = sub.add_parser("sales", help="Collect monthly sales rankings")
    p_sales.add_argument(
        "--months",
        type=int,
        default=6,
        choices=range(1, 7),
        help="Number of recent months (1-6, default 6)",
    )
    p_sales.add_argument(
        "--db", default=DEFAULT_DB, help="Path to SQLite database file"
    )

    p_specs = sub.add_parser("specs", help="Collect config specs")
    p_specs.add_argument(
        "--mode",
        choices=["sales", "all"],
        default="sales",
        help="sales=hot-selling series, all=all brands (default sales)",
    )
    p_specs.add_argument("--all-years", action="store_true", help="Include discontinued model years")
    p_specs.add_argument(
        "--db", default=DEFAULT_DB, help="Path to SQLite database file"
    )

    p_all = sub.add_parser("all", help="Collect both sales and specs")
    p_all.add_argument(
        "--months",
        type=int,
        default=6,
        choices=range(1, 7),
        help="Number of recent months for sales (1-6, default 6)",
    )
    p_all.add_argument("--all-years", action="store_true", help="Include discontinued model years")
    p_all.add_argument(
        "--db", default=DEFAULT_DB, help="Path to SQLite database file"
    )

    args = parser.parse_args()
    conn = init_db(args.db)
```

- [ ] **第 3 步：更新 `all` 命令的调用，以传播 --all-years**

将：
```python
        elif args.command == "all":
            run_sales(conn, months=args.months)
            run_specs(conn, mode="sales")
```
替换为：
```python
        elif args.command == "all":
            run_sales(conn, months=args.months)
            run_specs(conn, mode="sales", only_on_sale=not args.all_years)
```

- [ ] **第 4 步：更新 specs 命令的调用**

将：
```python
        elif args.command == "specs":
            run_specs(conn, mode=args.mode)
```
替换为：
```python
        elif args.command == "specs":
            run_specs(conn, mode=args.mode, only_on_sale=not args.all_years)
```

- [ ] **第 5 步：验证 CLI 帮助**

```bash
uv run python -m src.fetch_to_db --help
uv run python -m src.fetch_to_db sales --help
uv run python -m src.fetch_to_db specs --help
uv run python -m src.fetch_to_db all --help
```

预期：显示每个子命令的 `--db` 或 `--all-years` 帮助信息

- [ ] **第 6 步：运行测试**

```bash
uv run pytest tests/test_pipeline_specs.py -v
```

预期：10 passed

- [ ] **第 7 步：提交**

```bash
git add src/fetch_to_db.py
git commit -m "feat: add --db flag to fetch_to_db CLI, propagate --all-years to all subcommand"
```

---

### 任务 9：更新 export/__main__.py CLI —— --db 和 --output

**文件：**
- 修改：`src/export/__main__.py:11,18-46`

- [ ] **第 1 步：从 db 导入 DEFAULT_DB**

在第 11 行之后（`from ..db import init_db`），添加 DEFAULT_DB 到导入：

```python
from ..db import init_db, DEFAULT_DB
```

- [ ] **第 2 步：用 --db 和 --output 替换 parser 定义**

当前 parser 设置在约第 18-46 行。用以下内容替换整个 parser 定义块（从 `parser = argparse.ArgumentParser(...)` 到 `args = parser.parse_args()`）：

```python
def main():
    setup()
    parser = argparse.ArgumentParser(description="Export database data to xlsx")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sales = sub.add_parser("sales", help="Export sales ranking")
    p_sales.add_argument(
        "--months",
        type=int,
        default=6,
        choices=range(1, 7),
        help="Number of recent months (1-6, default 6)",
    )
    p_sales.add_argument(
        "--top", type=int, default=50, help="Top N per sub-category (default 50)"
    )
    p_sales.add_argument(
        "--db", default=DEFAULT_DB, help="Path to input SQLite database"
    )
    p_sales.add_argument(
        "--output", default="output", help="Output directory for xlsx files"
    )

    p_specs = sub.add_parser("specs", help="Export all config specs as xlsx")
    p_specs.add_argument(
        "--db", default=DEFAULT_DB, help="Path to input SQLite database"
    )
    p_specs.add_argument(
        "--output", default="output", help="Output directory for xlsx files"
    )

    p_all = sub.add_parser("all", help="Export both sales and specs (default params)")
    p_all.add_argument(
        "--months",
        type=int,
        default=6,
        choices=range(1, 7),
        help="Number of recent months for sales (1-6, default 6)",
    )
    p_all.add_argument(
        "--top", type=int, default=50, help="Top N per sub-category (default 50)"
    )
    p_all.add_argument(
        "--db", default=DEFAULT_DB, help="Path to input SQLite database"
    )
    p_all.add_argument(
        "--output", default="output", help="Output directory for xlsx files"
    )

    args = parser.parse_args()
    conn = init_db(args.db)
```

- [ ] **第 3 步：更新调用，传递 --db、--output、--months、--top**

将现有的调用代码：
```python
    try:
        if args.command == "sales":
            run_sales_export(conn, months=args.months, top=args.top)
        elif args.command == "specs":
            run_specs_export(conn)
        elif args.command == "all":
            run_sales_export(conn)
            run_specs_export(conn)
    finally:
        conn.close()
```
替换为：
```python
    try:
        if args.command == "sales":
            run_sales_export(conn, months=args.months, top=args.top, output_dir=args.output)
        elif args.command == "specs":
            run_specs_export(conn, output_dir=args.output)
        elif args.command == "all":
            run_sales_export(conn, months=args.months, top=args.top, output_dir=args.output)
            run_specs_export(conn, output_dir=args.output)
    finally:
        conn.close()
```

- [ ] **第 4 步：验证 CLI 帮助**

```bash
uv run python -m src.export --help
uv run python -m src.export sales --help
uv run python -m src.export specs --help
uv run python -m src.export all --help
```

预期：显示每个子命令的 `--db` 和 `--output` 帮助信息

- [ ] **第 5 步：运行测试**

```bash
uv run pytest tests/test_pipeline_specs.py -v
```

预期：10 passed

- [ ] **第 6 步：提交**

```bash
git add src/export/__main__.py
git commit -m "feat: add --db and --output flags to export CLI, propagate to all subcommand"
```

---

### 任务 10：更新 export/sales.py —— 移除环境变量、修复 None 检查、动态文件名/标题

**文件：**
- 修改：`src/export/sales.py:9,12,21-22,75,86`
- 修改：`src/excel_writer.py:35`

- [ ] **第 1 步：移除 OUTPUT_DIR 环境变量（第 9 行）**

删除这一行：
```python
OUTPUT_DIR = os.environ.get("CARMIINE_OUTPUT", "output")
```

- [ ] **第 2 步：更新 run() 函数以使用 None 检查和时间戳（第 12-22 行）**

将：
```python
def run(conn, months=6, top=50, output_dir=None):
    """Export sales ranking to xlsx.

    Args:
        conn: sqlite3.Connection
        months: number of recent months (1-6)
        top: top N per sub-category
        output_dir: override output path
    """
    ts = datetime.now().strftime("%Y%m%d%H%M")
    out_dir = output_dir or os.path.join(OUTPUT_DIR, ts)
    filepath = os.path.join(out_dir, "汽车销量排行-近6个月.xlsx")
    os.makedirs(out_dir, exist_ok=True)
```
替换为：
```python
def run(conn, months=6, top=50, output_dir=None):
    """Export sales ranking to xlsx.

    Args:
        conn: sqlite3.Connection
        months: number of recent months (1-6)
        top: top N per sub-category
        output_dir: override output path
    """
    ts = datetime.now().strftime("%Y%m%d%H%M")
    if output_dir is None:
        output_dir = os.path.join("output", ts)
    filepath = os.path.join(output_dir, f"汽车销量排行-近{months}个月.xlsx")
    os.makedirs(output_dir, exist_ok=True)
```

- [ ] **第 3 步：更新 run() 中剩余的 `out_dir` 引用为 `output_dir`**

函数中 `out_dir` 出现了 3 次（第 22、23、24 行）。第 2 步已经处理了这 3 次。确认没有剩余的 `out_dir` 出现：

```bash
rg -nF "out_dir" src/export/sales.py
```

预期：无匹配结果。

- [ ] **第 4 步：更新第 75 行的字典键，使其与动态列标题匹配**

将：
```python
                "6个月总销量": sales,
```
替换为：
```python
                f"{months}个月总销量": sales,
```

- [ ] **第 5 步：更新第 86 行的排序键**

将：
```python
            items.sort(key=lambda x: x["6个月总销量"], reverse=True)
```
替换为：
```python
            items.sort(key=lambda x: x[f"{months}个月总销量"], reverse=True)
```

- [ ] **第 6 步：更新第 92 行对 write_sales_excel 的调用**

将：
```python
    write_sales_excel(output, filepath)
```
替换为：
```python
    write_sales_excel(output, filepath, months)
```

- [ ] **第 7 步：更新 excel_writer.py 第 35 行的列标题**

在 `src/excel_writer.py` 中，`write_sales_excel` 函数有一个硬编码的列标题。该函数需要接收月份数，或者列标题必须由调用者传入。最小的改动是：为 `write_sales_excel` 添加一个 `months` 参数。

将 `write_sales_excel` 签名（第 32 行）：
```python
def write_sales_excel(output, filepath):
```
替换为：
```python
def write_sales_excel(output, filepath, months=6):
```

并将第 35 行的列定义：
```python
    cols = ["排名", "车型名称", "品牌", "主机厂", "6个月总销量", "价格区间", "子分类"]
```
替换为：
```python
    cols = ["排名", "车型名称", "品牌", "主机厂", f"{months}个月总销量", "价格区间", "子分类"]
```



- [ ] **第 8 步：验证导入**

```bash
uv run python -c "from src.export.sales import run; print('import OK')"
```

- [ ] **第 9 步：运行测试**

```bash
uv run pytest tests/test_pipeline_specs.py -v
```

预期：10 passed

- [ ] **第 10 步：提交**

```bash
git add src/export/sales.py src/excel_writer.py
git commit -m "fix: dynamic export filename/header, remove CARMINE_OUTPUT env var, use None check for timestamp"
```

---

### 任务 11：更新 export/specs.py —— 移除环境变量、修复 None 检查

**文件：**
- 修改：`src/export/specs.py:10,13,20-21`

- [ ] **第 1 步：移除 OUTPUT_DIR 环境变量（第 10 行）**

删除这一行：
```python
OUTPUT_DIR = os.environ.get("CARMIINE_OUTPUT", "output")
```

- [ ] **第 2 步：更新 run() 函数（第 13-21 行）**

将：
```python
def run(conn, output_dir=None):
    """Export all config specs to xlsx files, one per series.

    Args:
        conn: sqlite3.Connection
        output_dir: override output path
    """
    ts = datetime.now().strftime("%Y%m%d%H%M")
    out_dir = output_dir or os.path.join(OUTPUT_DIR, ts, "配置表")
    os.makedirs(out_dir, exist_ok=True)
```
替换为：
```python
def run(conn, output_dir=None):
    """Export all config specs to xlsx files, one per series.

    Args:
        conn: sqlite3.Connection
        output_dir: override output path
    """
    ts = datetime.now().strftime("%Y%m%d%H%M")
    if output_dir is None:
        output_dir = os.path.join("output", ts)
    output_dir = os.path.join(output_dir, "配置表")
    os.makedirs(output_dir, exist_ok=True)
```

- [ ] **第 3 步：更新剩余的 `out_dir` 引用为 `output_dir`**

`out_dir` 在第 41 行（`dir_path = os.path.join(out_dir, ...)`）和第 103 行（`print(f"Output: {out_dir}")`）中还有另外两次出现。全部替换为 `output_dir`：

第 41 行：
```python
        dir_path = os.path.join(output_dir, manu_name, brand_name)
```

第 103 行：
```python
    print(f"Output: {output_dir}")
```

验证无残留：
```bash
rg -nF "out_dir" src/export/specs.py
```

预期：无匹配结果。

- [ ] **第 4 步：验证导入**

```bash
uv run python -c "from src.export.specs import run; print('import OK')"
```

- [ ] **第 5 步：运行测试**

```bash
uv run pytest tests/test_pipeline_specs.py -v
```

预期：10 passed

- [ ] **第 6 步：提交**

```bash
git add src/export/specs.py
git commit -m "fix: remove CARMINE_OUTPUT env var in export/specs.py, use None check for timestamp"
```

---

### 任务 12：更新 README.md

**文件：**
- 修改：`README.md`

- [ ] **第 1 步：更新快速开始部分的使用示例**

将当前的快速开始代码块替换为反映新标志的代码块。读取 `README.md` 找到对应章节。

```bash
# Windows 用户可直接双击 run.bat 进入交互菜单

uv sync

# 采集数据到数据库
uv run python -m src.fetch_to_db sales --months 6    # 最近6个月销量
uv run python -m src.fetch_to_db sales --db my.db --months 3  # 指定数据库路径
uv run python -m src.fetch_to_db specs --mode all    # 全品牌配置
uv run python -m src.fetch_to_db specs --all-years    # 含停售年款
uv run python -m src.fetch_to_db all                 # 全量（默认参数）

# 从数据库导出 xlsx
uv run python -m src.export sales --months 6 --top 50
uv run python -m src.export sales --db my.db --output reports/
uv run python -m src.export specs
uv run python -m src.export all --db data/car.db --output out/
```

- [ ] **第 2 步：移除配置章节中过时的 ONLY_ON_SALE 引用**

将：
```markdown
## 配置

| 变量 | 位置 | 说明 | 默认值 |
|------|------|------|--------|
| `ONLY_ON_SALE` | `pipeline/specs.py` 顶部 | 仅采集在售年款 | `True` |
| `CARMIINE_OUTPUT` | 环境变量 | 输出根目录 | `./output` |
```
替换为：
```markdown
## 配置

| 选项 | 命令 | 说明 | 默认值 |
|------|------|------|--------|
| `--all-years` | `fetch_to_db specs` | 含停售年款 | `False` |
| `--db` | `fetch_to_db` / `export` | 数据库文件路径 | `./output/carmine.db` |
| `--output` | `export` | xlsx 输出目录 | `./output` |
```

- [ ] **第 3 步：提交**

```bash
git add README.md
git commit -m "docs: update README for new CLI flags, remove env var references"
```

---

### 任务 13：端到端验证

- [ ] **第 1 步：使用自定义数据库路径运行采集管道（1 个月）**

```bash
rm -f output/carmine.db test_verify.db
uv run python -m src.fetch_to_db sales --months 1 --db test_verify.db
```

预期：打印品牌数量、车系数量、销量行数。创建了 `test_verify.db`。

- [ ] **第 2 步：使用自定义输出目录运行导出管道**

```bash
rm -rf test_output
uv run python -m src.export sales --months 1 --db test_verify.db --output test_output
```

预期：在 `test_output/{timestamp}/` 中创建了 xlsx 文件

- [ ] **第 3 步：验证导出的 xlsx 文件名与月份数匹配**

```bash
ls test_output/*/
```

预期：`汽车销量排行-近1个月.xlsx`

- [ ] **第 4 步：运行完整的测试套件**

```bash
uv run pytest tests/ -v
```

预期：10 passed

- [ ] **第 5 步：清理并提交**

```bash
rm -rf test_verify.db test_output
git add -A
git commit -m "test: end-to-end verification with custom --db and --output paths"
```
