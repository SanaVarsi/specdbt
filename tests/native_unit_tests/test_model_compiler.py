import pytest

from specdbt.native_unit_tests.model_compiler import UnitTestCompileError, compile_scenario
from specdbt.parser import parse_feature_text

SIMPLE_SOURCE = """Feature: F

  @unit
  Scenario: Simple
    Given the following rows in "raw_customers":
      | id | first_name |
      | 1  | Michael    |
    When the "stg_customers" model runs
    Then the "stg_customers" should produce the following rows:
      | customer_id | first_name |
      | 1           | Michael    |
"""


def test_compiles_model_name_given_and_expect():
    scenario = parse_feature_text(SIMPLE_SOURCE).scenarios[0]
    compiled = compile_scenario(scenario)
    assert compiled.model_name == "stg_customers"
    assert compiled.given == [
        {"input": "ref('raw_customers')", "rows": [{"id": 1, "first_name": "Michael"}]}
    ]
    assert compiled.expect_rows == [{"customer_id": 1, "first_name": "Michael"}]
    assert compiled.is_incremental is None


def test_tracks_original_steps_for_reporting():
    scenario = parse_feature_text(SIMPLE_SOURCE).scenarios[0]
    compiled = compile_scenario(scenario)
    assert len(compiled.given_steps) == 1
    assert compiled.given_steps[0].text.startswith('the following rows in "raw_customers"')
    assert compiled.when_step.text == 'the "stg_customers" model runs'
    assert compiled.then_step.text.startswith('the "stg_customers" should produce')


MULTI_GIVEN_SOURCE = """Feature: F

  @unit
  Scenario: Two inputs
    Given the following rows in "stg_orders":
      | order_id |
      | 1        |
    And the following rows in "stg_payments":
      | payment_id | order_id |
      | 1          | 1        |
    When the "orders" model runs
    Then the "orders" should produce the following rows:
      | order_id |
      | 1        |
"""


def test_multiple_given_steps_each_become_a_given_entry():
    scenario = parse_feature_text(MULTI_GIVEN_SOURCE).scenarios[0]
    compiled = compile_scenario(scenario)
    assert [g["input"] for g in compiled.given] == ["ref('stg_orders')", "ref('stg_payments')"]


INCREMENTAL_SOURCE = """Feature: F

  @unit @incremental_model
  Scenario: Incremental mode
    Given the following rows in "stg_orders":
      | order_id | order_date |
      | 2        | 2018-01-02 |
    And the following rows already in "order_history":
      | order_id | order_date |
      | 1        | 2018-01-01 |
    When the "order_history" model runs
    Then the "order_history" should produce the following rows:
      | order_id | order_date |
      | 2        | 2018-01-02 |
"""


def test_already_in_step_compiles_to_input_this_and_sets_is_incremental_true():
    scenario = parse_feature_text(INCREMENTAL_SOURCE).scenarios[0]
    compiled = compile_scenario(scenario)
    assert compiled.is_incremental is True
    expected_given = {"input": "this", "rows": [{"order_id": 1, "order_date": "2018-01-01"}]}
    assert expected_given in compiled.given


FULL_REFRESH_SOURCE = """Feature: F

  @unit @incremental_model
  Scenario: Full refresh mode
    Given the following rows in "stg_orders":
      | order_id |
      | 1        |
    When the "order_history" model runs
    Then the "order_history" should produce the following rows:
      | order_id |
      | 1        |
"""


def test_incremental_model_tag_without_already_in_step_sets_is_incremental_false():
    scenario = parse_feature_text(FULL_REFRESH_SOURCE).scenarios[0]
    compiled = compile_scenario(scenario)
    assert compiled.is_incremental is False


def test_no_incremental_model_tag_leaves_is_incremental_none_even_with_already_in_step():
    # @incremental_model is what turns "already in" wording into an actual
    # overrides block -- without the tag, is_incremental stays unset even if
    # an "already in" step is (unusually) present, matching spec §4.1
    # finding 8's exception being opt-in, not inferred from step wording alone.
    source_without_tag = INCREMENTAL_SOURCE.replace(" @incremental_model", "")
    scenario = parse_feature_text(source_without_tag).scenarios[0]
    compiled = compile_scenario(scenario)
    assert compiled.is_incremental is None


PROSE_THEN_SOURCE = """Feature: F

  @unit
  Scenario: Prose then has nothing to translate to
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then "m" should have 1 row
"""


def test_prose_then_step_raises_unit_test_compile_error():
    scenario = parse_feature_text(PROSE_THEN_SOURCE).scenarios[0]
    with pytest.raises(UnitTestCompileError, match="canonical"):
        compile_scenario(scenario)


MACRO_WHEN_SOURCE = """Feature: F

  @unit
  Scenario: Macro when step has no unit mechanism
    Given the following rows in "orders":
      | order_id |
      | 1        |
    When the "select order_id from orders" macro runs
    Then the "select order_id from orders" should produce the following rows:
      | order_id |
      | 1        |
"""


def test_macro_when_step_raises_unit_test_compile_error_naming_dbt_core_10547():
    scenario = parse_feature_text(MACRO_WHEN_SOURCE).scenarios[0]
    with pytest.raises(UnitTestCompileError, match="dbt-core#10547"):
        compile_scenario(scenario)


NO_THEN_SOURCE = """Feature: F

  @unit
  Scenario: Missing then
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
"""


def test_scenario_with_no_then_step_raises_unit_test_compile_error():
    scenario = parse_feature_text(NO_THEN_SOURCE).scenarios[0]
    with pytest.raises(UnitTestCompileError, match="no row-table Then"):
        compile_scenario(scenario)
