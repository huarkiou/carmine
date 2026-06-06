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
