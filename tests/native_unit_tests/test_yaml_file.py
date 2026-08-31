from pathlib import Path

import yaml

from specdbt.native_unit_tests.yaml_file import (
    delete_unit_test_yaml,
    render_unit_test_yaml,
    unit_test_name,
    write_unit_test_yaml,
)


def test_unit_test_name_derived_from_run_id():
    assert unit_test_name("abc123") == "_specdbt_abc123"


def test_render_unit_test_yaml_structure_for_a_simple_model():
    text = render_unit_test_yaml(
        run_id="abc123",
        model_name="stg_customers",
        given=[{"input": "ref('raw_customers')", "rows": [{"id": 1, "first_name": "a"}]}],
        expect_rows=[{"customer_id": 1}],
        is_incremental=None,
    )
    parsed = yaml.safe_load(text)
    assert parsed == {
        "unit_tests": [
            {
                "name": "_specdbt_abc123",
                "model": "stg_customers",
                "given": [
                    {"input": "ref('raw_customers')", "rows": [{"id": 1, "first_name": "a"}]}
                ],
                "expect": {"rows": [{"customer_id": 1}]},
            }
        ]
    }


def test_render_unit_test_yaml_includes_is_incremental_override_when_given():
    text = render_unit_test_yaml(
        run_id="abc123", model_name="m", given=[], expect_rows=[], is_incremental=True
    )
    parsed = yaml.safe_load(text)
    assert parsed["unit_tests"][0]["overrides"] == {"macros": {"is_incremental": True}}


def test_render_unit_test_yaml_omits_overrides_when_is_incremental_is_none():
    text = render_unit_test_yaml(
        run_id="abc123", model_name="m", given=[], expect_rows=[], is_incremental=None
    )
    parsed = yaml.safe_load(text)
    assert "overrides" not in parsed["unit_tests"][0]


def test_render_unit_test_yaml_supports_input_this():
    text = render_unit_test_yaml(
        run_id="abc123",
        model_name="incr",
        given=[{"input": "this", "rows": [{"id": 1}]}],
        expect_rows=[{"id": 2}],
        is_incremental=True,
    )
    parsed = yaml.safe_load(text)
    assert parsed["unit_tests"][0]["given"] == [{"input": "this", "rows": [{"id": 1}]}]


def test_write_and_delete_unit_test_yaml(tmp_path: Path):
    path = write_unit_test_yaml(tmp_path, "abc123", "unit_tests: []\n")
    assert path == tmp_path / "models" / "_specdbt_abc123.yml"
    assert path.read_text() == "unit_tests: []\n"
    delete_unit_test_yaml(path)
    assert not path.exists()


def test_write_unit_test_yaml_respects_custom_model_paths_dir(tmp_path: Path):
    # Must not hardcode "models" -- a non-default model-paths dir needs the
    # generated YAML written where dbt will actually parse it.
    path = write_unit_test_yaml(tmp_path, "abc123", "unit_tests: []\n", model_paths_dir="transform")
    assert path == tmp_path / "transform" / "_specdbt_abc123.yml"
    assert path.read_text() == "unit_tests: []\n"


def test_delete_unit_test_yaml_is_a_noop_if_already_gone(tmp_path: Path):
    delete_unit_test_yaml(tmp_path / "models" / "does_not_exist.yml")  # must not raise
