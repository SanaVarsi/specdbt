# specdbt Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 0 skeleton — Gherkin parser → Fixture Builder → `ExecutionAdapter` interface + `FakeAdapter` → Assertion Engine → Reporter → CLI — end to end, proven against 5 hand-written `.feature` files targeting real data-pulse models.

**Architecture:** Small, single-responsibility modules under `src/specdbt/`, each with its own pytest file. `runner.py` wires parser→fixtures→adapter→assertions→reporter together; `cli.py` is a thin click layer over `runner.py`. No real SQL/Polars execution in this phase — `FakeAdapter` returns pre-registered hardcoded rows only.

**Tech Stack:** Python ≥3.12, `uv` (env/deps/build), `gherkin-official` (parsing), `click` (CLI), `pytest` + `ruff` (dev). Build backend: `hatchling`, src layout.

**Spec:** `docs/superpowers/specs/2026-08-23-specdbt-phase0-design.md`

## Global Constraints

- Python `>=3.12`; repo lives at `~/dev/specdbt`, independent git repo, **local commits only, never push**.
- Runtime deps: `gherkin-official>=42.0.1`, `click>=8.4.2`. Dev deps: `pytest>=9.1.1`, `ruff>=0.16.4`. All four checked 2026-08-23: actively maintained (official orgs — Cucumber team, Pallets, pytest-dev, Astral), recent releases, zero known vulnerabilities per OSV.dev for these exact versions. Any *new* dependency added beyond this list must get the same check (PyPI metadata sanity + OSV/`pip-audit` lookup) before it's added — report what was checked.
- License: MIT. Copyright holder: `SanaVarsi` (matches this machine's git identity — verify with `git config user.name` before writing `LICENSE` if this plan is ever reused elsewhere).
- No AI features implemented (`src/specdbt/ai/` is stubs only, `NotImplementedError`). No real SQL/Polars/DuckDB execution (`PolarsAdapter`/`DuckDBAdapter` don't exist yet — Phase 1). No CI config (needs a remote; out of scope).
- **Deviation from spec, disclosed here:** the spec's §4 described one shared `examples/data_pulse/features/canned_results.py`. Implementation instead uses a **per-feature-file naming convention**: `foo.feature` pairs with an optional co-located `foo.canned.py` exposing `CANNED_RESULTS: dict[str, ExecutionResult]`, and the CLI builds a **fresh `FakeAdapter` per feature file**. Reason: `FakeAdapter` maps `model_name → one canned result`; a single shared registry can't hold two different canned outputs for the same real model name (e.g. `silver_weather` needs a different canned result in each of its two scenarios). Per-file registries solve this with no added complexity in `FakeAdapter` itself, at the cost of one scenario per `.feature` file in Phase 0 — acceptable since Phase 1's real adapters compute results from fixtures instead of a static lookup and this constraint disappears then. `Fixture` also lives in `fixtures.py` (not `adapters/base.py` as the spec's literal code snippet placed it) since it's the Fixture Builder's own output type; `adapters/base.py` imports it. Shape of both dataclasses is unchanged from the spec.

---

## File Structure

```
specdbt/
├── src/specdbt/
│   ├── __init__.py
│   ├── py.typed
│   ├── typing_utils.py         # Task 2
│   ├── parser.py                # Task 3
│   ├── fixtures.py              # Task 4 (defines Fixture)
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py              # Task 5 (ExecutionAdapter, ExecutionResult)
│   │   └── fake_adapter.py      # Task 6
│   ├── assertions.py            # Task 7
│   ├── reporter.py              # Task 8
│   ├── runner.py                # Task 9
│   ├── cli.py                   # Task 10
│   └── ai/
│       ├── __init__.py
│       └── stubs.py             # Task 11
├── tests/
│   ├── test_typing_utils.py
│   ├── test_parser.py
│   ├── test_fixtures.py
│   ├── test_adapters.py
│   ├── test_assertions.py
│   ├── test_reporter.py
│   ├── test_runner.py
│   ├── test_cli.py
│   ├── test_ai_stubs.py
│   └── test_examples_data_pulse.py   # Task 12
├── examples/data_pulse/features/     # Task 12
│   ├── silver_weather_drops_null_timestamp.feature (+ .canned.py)
│   ├── silver_weather_casts_and_normalizes.feature (+ .canned.py)
│   ├── gold_weather_daily_aggregates_by_date.feature (+ .canned.py)
│   ├── gold_weather_anomalies_flags_outlier.feature (+ .canned.py)
│   └── gold_weather_anomalies_normal_reading.feature (+ .canned.py)
├── pyproject.toml                    # Task 1
├── .gitignore                        # Task 1
├── LICENSE                           # Task 1
└── README.md                         # Task 1 (stub), Task 12 (final)
```

---

### Task 1: Project scaffold + dependency security check

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `LICENSE`, `README.md` (stub), `src/specdbt/__init__.py`, `src/specdbt/py.typed`, `src/specdbt/adapters/__init__.py`, `src/specdbt/ai/__init__.py`

**Interfaces:**
- Produces: an importable, empty `specdbt` package installed in editable mode via `uv sync`; a `specdbt` console script entry point registered (not yet functional — `cli:cli` doesn't exist until Task 10, so leave `[project.scripts]` out of this task and add it in Task 10 instead, to avoid a broken entry point in between).

- [ ] **Step 1: Record the dependency security check**

Already performed 2026-08-23 (see Global Constraints). Confirm it still holds before proceeding — re-run:

```bash
for pkg_ver in "gherkin-official:42.0.1" "click:8.4.2" "pytest:9.1.1" "ruff:0.16.4"; do
  pkg="${pkg_ver%%:*}"; ver="${pkg_ver##*:}"
  echo "=== $pkg $ver ==="
  curl -s -X POST "https://api.osv.dev/v1/query" -H "Content-Type: application/json" \
    -d "{\"package\":{\"name\":\"${pkg}\",\"ecosystem\":\"PyPI\"},\"version\":\"${ver}\"}"
  echo
done
```

Expected: `{}` (no known vulnerabilities) for all four. If any return a non-empty `vulns` list, stop and pick a patched version or an alternative before continuing.

- [ ] **Step 2: Create the directory skeleton**

```bash
mkdir -p ~/dev/specdbt/src/specdbt/adapters ~/dev/specdbt/src/specdbt/ai ~/dev/specdbt/tests ~/dev/specdbt/examples/data_pulse/features
touch ~/dev/specdbt/src/specdbt/__init__.py
touch ~/dev/specdbt/src/specdbt/py.typed
touch ~/dev/specdbt/src/specdbt/adapters/__init__.py
touch ~/dev/specdbt/src/specdbt/ai/__init__.py
```

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[project]
name = "specdbt"
version = "0.1.0"
description = "BDD-style Given/When/Then testing for dbt models."
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
dependencies = [
    "gherkin-official>=42.0.1",
    "click>=8.4.2",
]

[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "ruff>=0.16.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/specdbt"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.py[cod]
.venv/
*.egg-info/
dist/
build/
.pytest_cache/
.ruff_cache/
.DS_Store
```

- [ ] **Step 5: Write `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 SanaVarsi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 6: Write a stub `README.md`** (Task 12 replaces this with the full version)

```markdown
# specdbt

BDD-style `Given`/`When`/`Then` testing for dbt models. Phase 0 in progress —
see `docs/superpowers/specs/2026-08-23-specdbt-phase0-design.md`.
```

- [ ] **Step 7: Sync the environment**

```bash
cd ~/dev/specdbt && uv sync
```

Expected: creates `.venv/` and `uv.lock`, installs `gherkin-official`, `click`, `pytest`, `ruff` with no errors.

- [ ] **Step 8: Full-environment vulnerability scan (catches transitive deps too)**

```bash
uv run --with pip-audit pip-audit
```

Expected: `No known vulnerabilities found`. If it reports any, stop and resolve before continuing (upgrade the flagged package via `uv add <pkg>@<fixed-version>` or find an alternative).

- [ ] **Step 9: Verify the package imports**

```bash
uv run python -c "import specdbt; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 10: Commit**

```bash
cd ~/dev/specdbt
git add pyproject.toml .gitignore LICENSE README.md src uv.lock
git commit -m "chore: scaffold specdbt project

Deps checked against OSV.dev 2026-08-23, zero known vulnerabilities:
gherkin-official 42.0.1, click 8.4.2, pytest 9.1.1, ruff 0.16.4.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `coerce_scalar` — shared text-to-scalar coercion

**Files:**
- Create: `src/specdbt/typing_utils.py`
- Test: `tests/test_typing_utils.py`

**Interfaces:**
- Produces: `coerce_scalar(text: str) -> bool | int | float | str`, used by Task 4 (`fixtures.py`) and Task 7 (`assertions.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_typing_utils.py
from specdbt.typing_utils import coerce_scalar


def test_coerces_integers():
    assert coerce_scalar("42") == 42
    assert isinstance(coerce_scalar("42"), int)


def test_coerces_floats():
    assert coerce_scalar("18.2") == 18.2
    assert isinstance(coerce_scalar("18.2"), float)


def test_coerces_booleans():
    assert coerce_scalar("true") is True
    assert coerce_scalar("True") is True
    assert coerce_scalar("false") is False
    assert coerce_scalar("False") is False


def test_leaves_plain_strings_as_strings():
    assert coerce_scalar("brightsky") == "brightsky"


def test_leaves_empty_string_as_empty_string():
    assert coerce_scalar("") == ""
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_typing_utils.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.typing_utils'`.

- [ ] **Step 3: Implement**

```python
# src/specdbt/typing_utils.py
"""Shared scalar-value coercion for Gherkin cell/literal text -> Python types."""

from __future__ import annotations

Scalar = bool | int | float | str


def coerce_scalar(text: str) -> Scalar:
    """Best-effort coercion of a Gherkin cell or literal string to bool, int,
    float, or (falling through) str. Order matters: bool checked before int/float
    since Python's int()/float() don't accept "true"/"false"."""
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/test_typing_utils.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/typing_utils.py tests/test_typing_utils.py
git commit -m "feat: add coerce_scalar text-to-scalar coercion

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Gherkin parser wrapper

**Files:**
- Create: `src/specdbt/parser.py`
- Test: `tests/test_parser.py`

**Interfaces:**
- Consumes: `gherkin.parser.Parser` (from the `gherkin-official` package — real API verified: `Parser().parse(source: str) -> dict` raises `gherkin.errors.CompositeParserException` on invalid syntax; returns `{"comments": []}` with no `"feature"` key for empty/feature-less source).
- Produces: `Step(keyword: str, type: str, text: str, table: list[list[str]])`, `Scenario(name: str, steps: list[Step])`, `Feature(name: str, scenarios: list[Scenario])`, `parse_feature_text(source: str) -> Feature`, `parse_feature_file(path: Path) -> Feature`, `FeatureParseError(ValueError)`. `Step.type` is one of `"Context"` (Given), `"Action"` (When), `"Outcome"` (Then) — `And`/`But` steps (`keywordType == "Conjunction"` in the raw AST) inherit the type of the nearest preceding non-conjunction step in the same scenario. `Step.keyword` is the raw keyword with whitespace stripped (`"Given"`, `"When"`, `"Then"`, `"And"`, `"But"`). `Step.table` is `[]` when the step has no data table, otherwise a list of rows (first row = header) of raw cell strings — **not** coerced to scalars here (Task 4 does that).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_parser.py
from pathlib import Path

import pytest

from specdbt.parser import FeatureParseError, parse_feature_file, parse_feature_text

SAMPLE = """Feature: Weather station deduplication

  Scenario: Duplicate rows collapse to one
    Given the following rows in "raw_weather_stations":
      | station_id | source     |
      | BER-001    | brightsky  |
    When the "stg_weather_stations" model runs
    Then "stg_weather_stations" should have 1 row
    And the row for station_id "BER-001" should have source "brightsky"
"""


def test_parses_feature_and_scenario_names():
    feature = parse_feature_text(SAMPLE)
    assert feature.name == "Weather station deduplication"
    assert len(feature.scenarios) == 1
    assert feature.scenarios[0].name == "Duplicate rows collapse to one"


def test_step_keywords_and_types_in_order():
    scenario = parse_feature_text(SAMPLE).scenarios[0]
    assert [s.keyword for s in scenario.steps] == ["Given", "When", "Then", "And"]
    assert [s.type for s in scenario.steps] == ["Context", "Action", "Outcome", "Outcome"]


def test_conjunction_step_inherits_previous_type():
    # the "And" step above follows a "Then" (Outcome) step and must inherit "Outcome"
    scenario = parse_feature_text(SAMPLE).scenarios[0]
    assert scenario.steps[3].type == "Outcome"
    assert (
        scenario.steps[3].text == 'the row for station_id "BER-001" should have source "brightsky"'
    )


def test_data_table_captured_as_raw_rows():
    scenario = parse_feature_text(SAMPLE).scenarios[0]
    assert scenario.steps[0].table == [
        ["station_id", "source"],
        ["BER-001", "brightsky"],
    ]


def test_step_without_table_has_empty_table():
    scenario = parse_feature_text(SAMPLE).scenarios[0]
    assert scenario.steps[1].table == []


def test_rejects_invalid_gherkin_syntax():
    with pytest.raises(FeatureParseError):
        parse_feature_text("this is not gherkin at all !!! ###")


def test_rejects_source_with_no_feature_keyword():
    with pytest.raises(FeatureParseError):
        parse_feature_text("")


def test_parse_feature_file_reads_from_disk(tmp_path: Path):
    feature_file = tmp_path / "example.feature"
    feature_file.write_text(SAMPLE)
    feature = parse_feature_file(feature_file)
    assert feature.name == "Weather station deduplication"
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_parser.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.parser'`.

- [ ] **Step 3: Implement**

```python
# src/specdbt/parser.py
"""Gherkin -> lightweight AST wrapper around gherkin-official.

Wraps `gherkin.parser.Parser` (the same reference parser Cucumber/behave/
pytest-bdd use) so the rest of specdbt never touches gherkin-official's raw
dict-based AST directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gherkin.errors import CompositeParserException
from gherkin.parser import Parser as _GherkinParser


@dataclass
class Step:
    keyword: str
    type: str  # "Context" | "Action" | "Outcome"
    text: str
    table: list[list[str]] = field(default_factory=list)


@dataclass
class Scenario:
    name: str
    steps: list[Step] = field(default_factory=list)


@dataclass
class Feature:
    name: str
    scenarios: list[Scenario] = field(default_factory=list)


class FeatureParseError(ValueError):
    """Raised when a .feature file/string can't be parsed."""


def parse_feature_text(source: str) -> Feature:
    try:
        doc = _GherkinParser().parse(source)
    except CompositeParserException as exc:
        raise FeatureParseError(str(exc)) from exc

    feature_node = doc.get("feature")
    if feature_node is None:
        raise FeatureParseError("no 'Feature:' found in source")

    scenarios: list[Scenario] = []
    for child in feature_node["children"]:
        scenario_node = child.get("scenario")
        if scenario_node is None:
            continue  # Background / Rule not supported in Phase 0
        steps: list[Step] = []
        last_type = "Context"
        for step_node in scenario_node["steps"]:
            step_type = step_node["keywordType"]
            if step_type == "Conjunction":
                step_type = last_type
            else:
                last_type = step_type
            data_table = step_node.get("dataTable")
            table = (
                [[cell["value"] for cell in row["cells"]] for row in data_table["rows"]]
                if data_table is not None
                else []
            )
            steps.append(
                Step(
                    keyword=step_node["keyword"].strip(),
                    type=step_type,
                    text=step_node["text"],
                    table=table,
                )
            )
        scenarios.append(Scenario(name=scenario_node["name"], steps=steps))

    return Feature(name=feature_node["name"], scenarios=scenarios)


def parse_feature_file(path: Path) -> Feature:
    return parse_feature_text(Path(path).read_text())
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/test_parser.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/parser.py tests/test_parser.py
git commit -m "feat: add Gherkin parser wrapper

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Fixture Builder

**Files:**
- Create: `src/specdbt/fixtures.py`
- Test: `tests/test_fixtures.py`

**Interfaces:**
- Consumes: `Step` from Task 3 (`specdbt.parser`), `coerce_scalar` from Task 2 (`specdbt.typing_utils`).
- Produces: `Fixture(name: str, rows: list[dict])`, `build_fixture(step: Step) -> Fixture`, `FixtureBuildError(ValueError)`. `Fixture` is imported by Task 5 (`adapters/base.py`) and used throughout.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fixtures.py
import pytest

from specdbt.fixtures import FixtureBuildError, build_fixture
from specdbt.parser import Step


def test_builds_fixture_with_typed_rows():
    step = Step(
        keyword="Given",
        type="Context",
        text='the following rows in "raw_weather_stations":',
        table=[
            ["station_id", "temp_c", "is_valid"],
            ["BER-001", "18.2", "true"],
        ],
    )
    fixture = build_fixture(step)
    assert fixture.name == "raw_weather_stations"
    assert fixture.rows == [{"station_id": "BER-001", "temp_c": 18.2, "is_valid": True}]


def test_rejects_non_context_step():
    step = Step(keyword="When", type="Action", text="the model runs", table=[])
    with pytest.raises(FixtureBuildError):
        build_fixture(step)


def test_rejects_step_text_that_does_not_match_the_given_pattern():
    step = Step(
        keyword="Given",
        type="Context",
        text="something else entirely",
        table=[["a"], ["1"]],
    )
    with pytest.raises(FixtureBuildError):
        build_fixture(step)


def test_rejects_given_step_with_no_table():
    step = Step(
        keyword="Given",
        type="Context",
        text='the following rows in "raw_weather_stations":',
        table=[],
    )
    with pytest.raises(FixtureBuildError):
        build_fixture(step)
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_fixtures.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.fixtures'`.

- [ ] **Step 3: Implement**

```python
# src/specdbt/fixtures.py
"""Fixture Builder: turns a Given step's data table into a typed Fixture."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from specdbt.parser import Step
from specdbt.typing_utils import coerce_scalar

_GIVEN_ROWS_RE = re.compile(r'the following rows in "([^"]+)":')


@dataclass
class Fixture:
    name: str
    rows: list[dict] = field(default_factory=list)


class FixtureBuildError(ValueError):
    """Raised when a Given step's text/table can't be turned into a Fixture."""


def build_fixture(step: Step) -> Fixture:
    if step.type != "Context":
        raise FixtureBuildError(f"expected a Given step, got a {step.type} step: {step.text!r}")

    match = _GIVEN_ROWS_RE.search(step.text)
    if match is None:
        raise FixtureBuildError(
            f"Given step text does not match the supported fixture pattern: {step.text!r}"
        )
    if not step.table:
        raise FixtureBuildError(f"Given step has no data table: {step.text!r}")

    name = match.group(1)
    header, *data_rows = step.table
    rows = [
        {column: coerce_scalar(value) for column, value in zip(header, row, strict=True)}
        for row in data_rows
    ]
    return Fixture(name=name, rows=rows)
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/test_fixtures.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/fixtures.py tests/test_fixtures.py
git commit -m "feat: add Fixture Builder

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: `ExecutionAdapter` interface

**Files:**
- Create: `src/specdbt/adapters/base.py`
- Test: `tests/test_adapters.py` (this task adds the first tests in this file; Task 6 appends more)

**Interfaces:**
- Consumes: `Fixture` from Task 4 (`specdbt.fixtures`).
- Produces: `ExecutionResult(rows: list[dict], row_count: int, raw: object = None)` with classmethod `ExecutionResult.of(rows: list[dict], raw: object = None) -> ExecutionResult` (derives `row_count = len(rows)`), and the abstract base `ExecutionAdapter` with `run_model(self, model_name: str, fixtures: list[Fixture]) -> ExecutionResult`. This is the single interface every future adapter (Task 6's `FakeAdapter`, and Phase 1's `PolarsAdapter`/`DuckDBAdapter`) implements — the engine-agnostic boundary from the spec.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_adapters.py
import pytest

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult


def test_execution_result_of_derives_row_count():
    result = ExecutionResult.of(rows=[{"a": 1}, {"a": 2}])
    assert result.row_count == 2
    assert result.raw is None


def test_execution_result_of_handles_empty_rows():
    result = ExecutionResult.of(rows=[])
    assert result.row_count == 0


def test_execution_adapter_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ExecutionAdapter()  # type: ignore[abstract]
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_adapters.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.adapters.base'`.

- [ ] **Step 3: Implement**

```python
# src/specdbt/adapters/base.py
"""Execution adapter interface — the engine-agnostic boundary. Every concrete
adapter (FakeAdapter now; PolarsAdapter/DuckDBAdapter/DbtCoreAdapter later)
implements this and nothing above it needs to know which one is in use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from specdbt.fixtures import Fixture


@dataclass
class ExecutionResult:
    rows: list[dict]
    row_count: int
    raw: object = None

    @classmethod
    def of(cls, rows: list[dict], raw: object = None) -> "ExecutionResult":
        """Convenience constructor: row_count is derived from len(rows)."""
        return cls(rows=rows, row_count=len(rows), raw=raw)


class ExecutionAdapter(ABC):
    @abstractmethod
    def run_model(self, model_name: str, fixtures: list[Fixture]) -> ExecutionResult:
        """Run `model_name` with the given fixtures substituted for its
        refs/sources, and return the resulting rows."""
        raise NotImplementedError
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/test_adapters.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/adapters/base.py tests/test_adapters.py
git commit -m "feat: add ExecutionAdapter interface and ExecutionResult

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: `FakeAdapter`

**Files:**
- Modify: `tests/test_adapters.py` (append)
- Create: `src/specdbt/adapters/fake_adapter.py`

**Interfaces:**
- Consumes: `ExecutionAdapter`, `ExecutionResult` from Task 5; `Fixture` from Task 4.
- Produces: `FakeAdapter` with `register(model_name: str, result: ExecutionResult) -> None` and `run_model(model_name, fixtures) -> ExecutionResult` (looks up the registry, ignores `fixtures` entirely); `ModelNotRegisteredError(KeyError)`. Used by Task 9 (`runner.py`) and Task 10 (`cli.py`).

- [ ] **Step 1: Append the failing tests**

```python
# tests/test_adapters.py  (append to the file from Task 5)
from specdbt.adapters.fake_adapter import FakeAdapter, ModelNotRegisteredError
from specdbt.fixtures import Fixture


def test_fake_adapter_returns_registered_result():
    adapter = FakeAdapter()
    result = ExecutionResult.of(rows=[{"a": 1}])
    adapter.register("my_model", result)
    assert adapter.run_model("my_model", fixtures=[]) is result


def test_fake_adapter_raises_for_unregistered_model():
    adapter = FakeAdapter()
    with pytest.raises(ModelNotRegisteredError):
        adapter.run_model("missing_model", fixtures=[])


def test_fake_adapter_ignores_fixtures_content():
    adapter = FakeAdapter()
    result = ExecutionResult.of(rows=[{"a": 1}])
    adapter.register("m", result)
    fixture = Fixture(name="raw", rows=[{"x": 1}])
    assert adapter.run_model("m", fixtures=[fixture]) is result
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_adapters.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.adapters.fake_adapter'`.

- [ ] **Step 3: Implement**

```python
# src/specdbt/adapters/fake_adapter.py
"""Phase 0's only concrete adapter: returns pre-registered canned results,
never computes anything from the fixtures it's given. Proves the pipeline
plumbing; Phase 1's PolarsAdapter/DuckDBAdapter provide real correctness.
"""

from __future__ import annotations

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.fixtures import Fixture


class ModelNotRegisteredError(KeyError):
    """Raised when run_model() is asked for a model with no canned result registered."""


class FakeAdapter(ExecutionAdapter):
    def __init__(self) -> None:
        self._canned_results: dict[str, ExecutionResult] = {}

    def register(self, model_name: str, result: ExecutionResult) -> None:
        self._canned_results[model_name] = result

    def run_model(self, model_name: str, fixtures: list[Fixture]) -> ExecutionResult:
        try:
            return self._canned_results[model_name]
        except KeyError:
            raise ModelNotRegisteredError(
                f"no canned result registered for model {model_name!r}"
            ) from None
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/test_adapters.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/adapters/fake_adapter.py tests/test_adapters.py
git commit -m "feat: add FakeAdapter

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: Assertion engine

**Files:**
- Create: `src/specdbt/assertions.py`
- Test: `tests/test_assertions.py`

**Interfaces:**
- Consumes: `ExecutionResult` from Task 5, `coerce_scalar` from Task 2.
- Produces: `AssertionFailure(AssertionError)` (with `.expected`/`.actual` attributes), `UnrecognizedStepError(ValueError)`, `ThenContext(results: dict[str, ExecutionResult], last_model: str | None)`, `evaluate_then_step(text: str, ctx: ThenContext) -> None` (raises on failure/unrecognized, returns `None` on success). Used by Task 9 (`runner.py`).

Supported step patterns (spec §4):
```
"<model>" should have <N> row(s)
column "<col>" in "<model>" should not contain nulls
column "<col>" in "<model>" should be unique
the row for <key_col> "<key_val>" should have <col> <value>
```
(text passed to `evaluate_then_step` has the `Then `/`And `/`But ` keyword already stripped, per Task 3's `Step.text`.) The last pattern has no `<model>` in its text — it checks against `ctx.last_model`, the model named by the most recent `When` step in the scenario.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_assertions.py
import pytest

from specdbt.adapters.base import ExecutionResult
from specdbt.assertions import (
    AssertionFailure,
    ThenContext,
    UnrecognizedStepError,
    evaluate_then_step,
)


@pytest.fixture
def sample_result():
    return ExecutionResult.of(
        rows=[
            {"station_id": "BER-001", "source": "brightsky", "temp_c": 18.2},
            {"station_id": "BER-002", "source": "dwd_backup", "temp_c": 17.9},
        ]
    )


def test_row_count_passes(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    evaluate_then_step('"stg" should have 2 rows', ctx)


def test_row_count_fails(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('"stg" should have 5 rows', ctx)


def test_not_null_passes(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    evaluate_then_step('column "source" in "stg" should not contain nulls', ctx)


def test_not_null_fails():
    result = ExecutionResult.of(rows=[{"source": None}])
    ctx = ThenContext(results={"stg": result}, last_model="stg")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('column "source" in "stg" should not contain nulls', ctx)


def test_unique_passes(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    evaluate_then_step('column "station_id" in "stg" should be unique', ctx)


def test_unique_fails():
    result = ExecutionResult.of(rows=[{"station_id": "BER-001"}, {"station_id": "BER-001"}])
    ctx = ThenContext(results={"stg": result}, last_model="stg")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('column "station_id" in "stg" should be unique', ctx)


def test_row_field_string_value_passes(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    evaluate_then_step('the row for station_id "BER-001" should have source "brightsky"', ctx)


def test_row_field_numeric_value_passes(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    evaluate_then_step('the row for station_id "BER-001" should have temp_c 18.2', ctx)


def test_row_field_fails_on_value_mismatch(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('the row for station_id "BER-001" should have source "dwd_backup"', ctx)


def test_row_field_fails_when_no_row_matches_key(sample_result):
    ctx = ThenContext(results={"stg": sample_result}, last_model="stg")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('the row for station_id "BER-999" should have source "brightsky"', ctx)


def test_unrecognized_step_raises():
    ctx = ThenContext(results={}, last_model=None)
    with pytest.raises(UnrecognizedStepError):
        evaluate_then_step("something nobody implemented", ctx)


def test_referencing_a_model_that_has_not_run_raises_assertion_failure():
    ctx = ThenContext(results={}, last_model=None)
    with pytest.raises(AssertionFailure):
        evaluate_then_step('"nope" should have 1 row', ctx)
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_assertions.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.assertions'`.

- [ ] **Step 3: Implement**

```python
# src/specdbt/assertions.py
"""Then-step assertion library (Phase 0 subset — see spec §4)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from specdbt.adapters.base import ExecutionResult
from specdbt.typing_utils import coerce_scalar


class AssertionFailure(AssertionError):
    def __init__(self, message: str, expected: object = None, actual: object = None) -> None:
        super().__init__(message)
        self.expected = expected
        self.actual = actual


class UnrecognizedStepError(ValueError):
    """Raised when a Then/And/But step's text matches none of the known patterns."""


_ROW_COUNT_RE = re.compile(r'^"([^"]+)" should have (\d+) rows?$')
_NOT_NULL_RE = re.compile(r'^column "([^"]+)" in "([^"]+)" should not contain nulls$')
_UNIQUE_RE = re.compile(r'^column "([^"]+)" in "([^"]+)" should be unique$')
_ROW_FIELD_RE = re.compile(r'^the row for (\w+) "([^"]+)" should have (\w+) (.+)$')


@dataclass
class ThenContext:
    """What a Then/And/But step needs: every named result produced so far in the
    scenario, and the most recently produced one (for steps that don't name a
    model explicitly, like "the row for X should have Y")."""

    results: dict[str, ExecutionResult]
    last_model: str | None


def evaluate_then_step(text: str, ctx: ThenContext) -> None:
    """Raise AssertionFailure if the expectation doesn't hold, or
    UnrecognizedStepError if the text matches no known pattern. None on success."""
    if (m := _ROW_COUNT_RE.match(text)) is not None:
        model_name, expected_count = m.group(1), int(m.group(2))
        result = _lookup(ctx, model_name)
        if result.row_count != expected_count:
            raise AssertionFailure(
                f'expected "{model_name}" to have {expected_count} row(s), got {result.row_count}',
                expected=expected_count,
                actual=result.row_count,
            )
        return

    if (m := _NOT_NULL_RE.match(text)) is not None:
        column, model_name = m.group(1), m.group(2)
        result = _lookup(ctx, model_name)
        nulls = [row for row in result.rows if row.get(column) is None]
        if nulls:
            raise AssertionFailure(
                f'expected column "{column}" in "{model_name}" to contain no nulls, '
                f"found {len(nulls)}",
                expected="no nulls",
                actual=f"{len(nulls)} null row(s)",
            )
        return

    if (m := _UNIQUE_RE.match(text)) is not None:
        column, model_name = m.group(1), m.group(2)
        result = _lookup(ctx, model_name)
        values = [row.get(column) for row in result.rows]
        duplicates = sorted({v for v in values if values.count(v) > 1}, key=str)
        if duplicates:
            raise AssertionFailure(
                f'expected column "{column}" in "{model_name}" to be unique, '
                f"found duplicate(s) {duplicates}",
                expected="unique values",
                actual=f"duplicates: {duplicates}",
            )
        return

    if (m := _ROW_FIELD_RE.match(text)) is not None:
        key_col, key_val_raw, field_name, raw_value = m.groups()
        if ctx.last_model is None:
            raise AssertionFailure(f"no model has run yet to check a row against: {text!r}")
        result = _lookup(ctx, ctx.last_model)
        key_val = coerce_scalar(key_val_raw)
        matches = [row for row in result.rows if row.get(key_col) == key_val]
        if not matches:
            raise AssertionFailure(
                f'no row found where {key_col} == {key_val_raw!r} in "{ctx.last_model}"',
                expected=f"a row with {key_col}={key_val_raw!r}",
                actual="no matching row",
            )
        expected_value = coerce_scalar(raw_value.strip('"'))
        actual_value = matches[0].get(field_name)
        if actual_value != expected_value:
            raise AssertionFailure(
                f"expected {field_name} {expected_value!r} for row {key_col}={key_val_raw!r}, "
                f"got {actual_value!r}",
                expected=expected_value,
                actual=actual_value,
            )
        return

    raise UnrecognizedStepError(f"no assertion pattern matches: {text!r}")


def _lookup(ctx: ThenContext, model_name: str) -> ExecutionResult:
    try:
        return ctx.results[model_name]
    except KeyError:
        raise AssertionFailure(f'model "{model_name}" has not run yet in this scenario') from None
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/test_assertions.py -v
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/assertions.py tests/test_assertions.py
git commit -m "feat: add Then-step assertion engine

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: Reporter

**Files:**
- Create: `src/specdbt/reporter.py`
- Test: `tests/test_reporter.py`

**Interfaces:**
- Produces: `StepResult(keyword: str, text: str, passed: bool, error: str | None = None)`, `ScenarioReport(name: str, steps: list[StepResult])` with `.passed` property, `FeatureReport(name: str, scenarios: list[ScenarioReport])`, `render_feature_report(report: FeatureReport) -> str`, `render_summary(reports: list[FeatureReport]) -> str`. Used by Task 9 (`runner.py` builds these) and Task 10 (`cli.py` renders them).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reporter.py
from specdbt.reporter import (
    FeatureReport,
    ScenarioReport,
    StepResult,
    render_feature_report,
    render_summary,
)


def test_scenario_report_passed_is_true_when_all_steps_pass():
    scenario = ScenarioReport(name="S", steps=[StepResult("Given", "x", True)])
    assert scenario.passed is True


def test_scenario_report_passed_is_false_when_any_step_fails():
    scenario = ScenarioReport(
        name="S", steps=[StepResult("Given", "x", True), StepResult("Then", "y", False, "boom")]
    )
    assert scenario.passed is False


def test_render_feature_report_shows_names_and_marks():
    report = FeatureReport(
        name="Weather source deduplication",
        scenarios=[
            ScenarioReport(
                name="One row survives",
                steps=[
                    StepResult("Given", "some rows", True),
                    StepResult("Then", "it fails", False, "expected 1, got 2"),
                ],
            )
        ],
    )
    text = render_feature_report(report)
    assert "Feature: Weather source deduplication" in text
    assert "Scenario: One row survives" in text
    assert "✓" in text
    assert "✗" in text
    assert "expected 1, got 2" in text


def test_render_summary_counts_scenarios_steps_and_failures():
    report = FeatureReport(
        name="F",
        scenarios=[
            ScenarioReport(
                name="S1",
                steps=[StepResult("Given", "a", True), StepResult("Then", "b", False, "x")],
            ),
            ScenarioReport(name="S2", steps=[StepResult("Given", "a", True)]),
        ],
    )
    assert render_summary([report]) == "2 scenario(s), 3 step(s), 1 failure(s)"
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_reporter.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.reporter'`.

- [ ] **Step 3: Implement**

```python
# src/specdbt/reporter.py
"""Terminal reporting: echoes scenarios back in their own Gherkin language,
with a pass/fail mark and error detail per step (spec §4)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StepResult:
    keyword: str
    text: str
    passed: bool
    error: str | None = None


@dataclass
class ScenarioReport:
    name: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(step.passed for step in self.steps)


@dataclass
class FeatureReport:
    name: str
    scenarios: list[ScenarioReport] = field(default_factory=list)


def render_feature_report(report: FeatureReport) -> str:
    lines = [f"Feature: {report.name}", ""]
    for scenario in report.scenarios:
        lines.append(f"  Scenario: {scenario.name}")
        for step in scenario.steps:
            mark = "✓" if step.passed else "✗"
            lines.append(f"    {step.keyword} {step.text}   {mark}")
            if not step.passed and step.error:
                lines.append(f"        {step.error}")
        lines.append("")
    return "\n".join(lines)


def render_summary(reports: list[FeatureReport]) -> str:
    scenario_count = sum(len(r.scenarios) for r in reports)
    steps = [step for r in reports for scenario in r.scenarios for step in scenario.steps]
    failures = sum(1 for step in steps if not step.passed)
    return f"{scenario_count} scenario(s), {len(steps)} step(s), {failures} failure(s)"
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/test_reporter.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/reporter.py tests/test_reporter.py
git commit -m "feat: add terminal reporter

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 9: Runner (pipeline orchestration)

**Files:**
- Create: `src/specdbt/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `parse_feature_text`/`Scenario` (Task 3), `build_fixture`/`Fixture` (Task 4), `ExecutionAdapter` (Task 5), `evaluate_then_step`/`ThenContext`/`AssertionFailure`/`UnrecognizedStepError` (Task 7), `StepResult`/`ScenarioReport`/`FeatureReport` (Task 8).
- Produces: `run_feature_text(source: str, adapter: ExecutionAdapter) -> FeatureReport`, `run_feature_file(path: Path, adapter: ExecutionAdapter) -> FeatureReport`. One `adapter` instance is shared across every scenario in one feature file (Task 10's CLI creates one `FakeAdapter` per **file**, not per scenario — see Global Constraints deviation note). A scenario stops at its first failing/erroring step (matches Cucumber's own behavior) — later steps in that scenario are not attempted or recorded.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_runner.py
from pathlib import Path

from specdbt.adapters.base import ExecutionResult
from specdbt.adapters.fake_adapter import FakeAdapter
from specdbt.runner import run_feature_file, run_feature_text

PASSING_SOURCE = """Feature: Dedup

  Scenario: One row survives
    Given the following rows in "raw_weather_stations":
      | station_id | source |
      | BER-001    | brightsky |
    When the "stg_weather_stations" model runs
    Then "stg_weather_stations" should have 1 row
    And the row for station_id "BER-001" should have source "brightsky"
"""


def test_run_feature_text_reports_all_passing_steps():
    adapter = FakeAdapter()
    adapter.register(
        "stg_weather_stations",
        ExecutionResult.of(rows=[{"station_id": "BER-001", "source": "brightsky"}]),
    )
    report = run_feature_text(PASSING_SOURCE, adapter)
    assert report.name == "Dedup"
    assert len(report.scenarios) == 1
    assert report.scenarios[0].passed is True
    assert len(report.scenarios[0].steps) == 4


FAILING_SOURCE = """Feature: F

  Scenario: Fails
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then "m" should have 1 row
    And the row for c "1" should have c 1
"""


def test_run_feature_text_stops_scenario_at_first_failed_step():
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[]))
    report = run_feature_text(FAILING_SOURCE, adapter)
    scenario = report.scenarios[0]
    assert scenario.passed is False
    assert len(scenario.steps) == 3  # Given, When, Then(fails) -- the And is never reached
    assert scenario.steps[-1].passed is False
    assert "expected" in scenario.steps[-1].error


UNREGISTERED_MODEL_SOURCE = """Feature: F

  Scenario: Missing model
    Given the following rows in "a":
      | c |
      | 1 |
    When the "missing" model runs
    Then "missing" should have 1 row
"""


def test_run_feature_text_reports_unregistered_model_as_a_failed_when_step():
    adapter = FakeAdapter()
    report = run_feature_text(UNREGISTERED_MODEL_SOURCE, adapter)
    scenario = report.scenarios[0]
    assert scenario.passed is False
    assert len(scenario.steps) == 2  # Given, When(fails) -- Then never reached
    assert scenario.steps[1].passed is False


def test_run_feature_file_reads_from_disk(tmp_path: Path):
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"c": 1}]))
    feature_file = tmp_path / "x.feature"
    feature_file.write_text(
        "Feature: F\n\n"
        "  Scenario: S\n"
        '    Given the following rows in "a":\n'
        "      | c |\n"
        "      | 1 |\n"
        '    When the "m" model runs\n'
        '    Then "m" should have 1 row\n'
    )
    report = run_feature_file(feature_file, adapter)
    assert report.scenarios[0].passed is True
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_runner.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.runner'`.

- [ ] **Step 3: Implement**

```python
# src/specdbt/runner.py
"""Wires parser -> fixtures -> adapter -> assertions -> reporter into one
pipeline (spec: docs/superpowers/specs/2026-08-23-specdbt-phase0-design.md)."""

from __future__ import annotations

import re
from pathlib import Path

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.assertions import ThenContext, evaluate_then_step
from specdbt.fixtures import Fixture, build_fixture
from specdbt.parser import Scenario, parse_feature_text
from specdbt.reporter import FeatureReport, ScenarioReport, StepResult

_WHEN_MODEL_RE = re.compile(r'the "([^"]+)" model runs$')


def run_feature_text(source: str, adapter: ExecutionAdapter) -> FeatureReport:
    feature = parse_feature_text(source)
    scenario_reports = [_run_scenario(scenario, adapter) for scenario in feature.scenarios]
    return FeatureReport(name=feature.name, scenarios=scenario_reports)


def run_feature_file(path: Path, adapter: ExecutionAdapter) -> FeatureReport:
    return run_feature_text(Path(path).read_text(), adapter)


def _run_scenario(scenario: Scenario, adapter: ExecutionAdapter) -> ScenarioReport:
    fixtures: dict[str, Fixture] = {}
    results: dict[str, ExecutionResult] = {}
    last_model: str | None = None
    step_results: list[StepResult] = []

    for step in scenario.steps:
        try:
            if step.type == "Context":
                fixture = build_fixture(step)
                fixtures[fixture.name] = fixture
            elif step.type == "Action":
                match = _WHEN_MODEL_RE.search(step.text)
                if match is None:
                    raise ValueError(f"no When-step pattern matches: {step.text!r}")
                model_name = match.group(1)
                results[model_name] = adapter.run_model(model_name, list(fixtures.values()))
                last_model = model_name
            else:  # "Outcome"
                evaluate_then_step(step.text, ThenContext(results=results, last_model=last_model))
        except Exception as exc:  # noqa: BLE001 -- any step-level error becomes a failed step
            step_results.append(StepResult(step.keyword, step.text, passed=False, error=str(exc)))
            break
        else:
            step_results.append(StepResult(step.keyword, step.text, passed=True))

    return ScenarioReport(name=scenario.name, steps=step_results)
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/test_runner.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/runner.py tests/test_runner.py
git commit -m "feat: add pipeline runner

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 10: CLI

**Files:**
- Create: `src/specdbt/cli.py`
- Modify: `pyproject.toml` (add `[project.scripts]`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `run_feature_file` (Task 9), `FakeAdapter` (Task 6), `ExecutionResult` (Task 5), `render_feature_report`/`render_summary` (Task 8).
- Produces: click group `cli` with commands `init [DIRECTORY]`, `run TARGET`, `generate --from-model` (stub), `compile TARGET --to` (stub). Console script `specdbt` → `specdbt.cli:cli`.
- Convention introduced here (see Global Constraints deviation note): `run` looks for `FEATURE.canned.py` next to each `FEATURE.feature` it runs, loads its `CANNED_RESULTS: dict[str, ExecutionResult]`, and registers them into a **fresh `FakeAdapter`** for that file before running its scenarios.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli.py
from pathlib import Path

from click.testing import CliRunner

from specdbt.cli import cli


def test_init_creates_example_feature_and_canned_files(tmp_path: Path):
    runner = CliRunner()
    target = tmp_path / "features"
    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code == 0, result.output
    assert (target / "example.feature").exists()
    assert (target / "example.canned.py").exists()


def test_init_refuses_to_overwrite_existing_scaffold(tmp_path: Path):
    runner = CliRunner()
    target = tmp_path / "features"
    runner.invoke(cli, ["init", str(target)])
    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_run_reports_pass_for_the_scaffolded_example(tmp_path: Path):
    runner = CliRunner()
    target = tmp_path / "features"
    runner.invoke(cli, ["init", str(target)])
    result = runner.invoke(cli, ["run", str(target)])
    assert result.exit_code == 0, result.output
    assert "✓" in result.output
    assert "0 failure(s)" in result.output


def test_run_exits_nonzero_when_a_scenario_fails(tmp_path: Path):
    feature = tmp_path / "bad.feature"
    feature.write_text(
        "Feature: F\n\n"
        "  Scenario: S\n"
        '    Given the following rows in "a":\n'
        "      | c |\n"
        "      | 1 |\n"
        '    When the "missing" model runs\n'
        '    Then "missing" should have 1 row\n'
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["run", str(feature)])
    assert result.exit_code == 1


def test_run_errors_when_no_feature_files_found(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["run", str(empty_dir)])
    assert result.exit_code != 0
    assert "no .feature files found" in result.output


def test_generate_reports_not_implemented():
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "--from-model", "x"])
    assert result.exit_code != 0
    assert "Phase 3" in result.output


def test_compile_reports_not_implemented(tmp_path: Path):
    feature = tmp_path / "x.feature"
    feature.write_text("Feature: F\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["compile", str(feature), "--to", "dbt-unit-tests"])
    assert result.exit_code != 0
    assert "Phase 2" in result.output
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.cli'`.

- [ ] **Step 3: Implement**

```python
# src/specdbt/cli.py
"""specdbt command-line interface."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import click

from specdbt.adapters.base import ExecutionResult
from specdbt.adapters.fake_adapter import FakeAdapter
from specdbt.reporter import render_feature_report, render_summary
from specdbt.runner import run_feature_file

_SCAFFOLD_FEATURE = """Feature: Example feature

  Scenario: Replace this with a real scenario
    Given the following rows in "example_source":
      | id | value |
      | 1  | hello |
    When the "example_model" model runs
    Then "example_model" should have 1 row
"""

_SCAFFOLD_CANNED = '''"""Hand-coded canned result for example.feature (Phase 0)."""
from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "example_model": ExecutionResult.of(rows=[{"id": 1, "value": "hello"}]),
}
'''


@click.group()
def cli() -> None:
    """specdbt -- BDD-style Given/When/Then testing for dbt models."""


@cli.command()
@click.argument("directory", type=click.Path(path_type=Path), default=Path("features"))
def init(directory: Path) -> None:
    """Scaffold DIRECTORY with one example .feature file and its canned result."""
    directory.mkdir(parents=True, exist_ok=True)
    example = directory / "example.feature"
    canned = example.with_suffix(".canned.py")
    if example.exists() or canned.exists():
        raise click.ClickException(f"{example} already exists, not overwriting")
    example.write_text(_SCAFFOLD_FEATURE)
    canned.write_text(_SCAFFOLD_CANNED)
    click.echo(f"created {example}")
    click.echo(f"created {canned}")


def _load_canned_results(path: Path) -> dict[str, ExecutionResult]:
    spec = importlib.util.spec_from_file_location(f"_specdbt_canned_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise click.ClickException(f"could not load {path} as a Python module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.CANNED_RESULTS
    except AttributeError:
        raise click.ClickException(f"{path} does not define CANNED_RESULTS") from None


@cli.command()
@click.argument("target", type=click.Path(path_type=Path, exists=True))
def run(target: Path) -> None:
    """Parse and run the .feature file(s) under TARGET (Phase 0: FakeAdapter only).

    Each FEATURE.feature file may have a co-located FEATURE.canned.py exposing
    CANNED_RESULTS: dict[str, ExecutionResult], pre-registered into a fresh
    FakeAdapter before that file's scenarios run.
    """
    paths = sorted(target.glob("*.feature")) if target.is_dir() else [target]
    if not paths:
        raise click.ClickException(f"no .feature files found under {target}")

    reports = []
    for path in paths:
        adapter = FakeAdapter()
        canned_path = path.with_suffix(".canned.py")
        if canned_path.exists():
            for model_name, result in _load_canned_results(canned_path).items():
                adapter.register(model_name, result)
        reports.append(run_feature_file(path, adapter))

    for report in reports:
        click.echo(render_feature_report(report))
    click.echo(render_summary(reports))

    if any(not scenario.passed for report in reports for scenario in report.scenarios):
        sys.exit(1)


@cli.command()
@click.option("--from-model", "from_model", required=True)
@click.option("--fixtures", "fixtures_flag", is_flag=True, default=False)
def generate(from_model: str, fixtures_flag: bool) -> None:
    """AI-assisted scenario/fixture generation (Phase 3 -- not implemented yet)."""
    raise click.ClickException(
        "`specdbt generate` ships in Phase 3 -- see the AI integration plan doc."
    )


@cli.command(name="compile")
@click.argument("target", type=click.Path(path_type=Path, exists=True))
@click.option("--to", "to_format", type=click.Choice(["dbt-unit-tests"]), required=True)
def compile_(target: Path, to_format: str) -> None:
    """Compile .feature scenarios to native dbt unit tests (Phase 2 -- not implemented yet)."""
    raise click.ClickException("`specdbt compile` ships in Phase 2 -- see the roadmap doc.")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Add the console-script entry point**

In `pyproject.toml`, add under `[project]`:

```toml
[project.scripts]
specdbt = "specdbt.cli:cli"
```

Then re-sync so the entry point is installed:

```bash
uv sync
```

- [ ] **Step 5: Run and confirm pass**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Manually verify the entry point works**

```bash
uv run specdbt init /tmp/specdbt-smoketest
uv run specdbt run /tmp/specdbt-smoketest
rm -rf /tmp/specdbt-smoketest
```

Expected: `init` prints two `created ...` lines; `run` prints a passing report ending in `1 scenario(s), 3 step(s), 0 failure(s)`.

- [ ] **Step 7: Commit**

```bash
git add src/specdbt/cli.py tests/test_cli.py pyproject.toml uv.lock
git commit -m "feat: add specdbt CLI (init, run, generate/compile stubs)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 11: AI layer stubs

**Files:**
- Create: `src/specdbt/ai/stubs.py`
- Test: `tests/test_ai_stubs.py`

**Interfaces:**
- Produces: `LLMClient.complete(prompt: str) -> str`, `generate_fixtures(model_sql: str, schema: dict[str, str], count: int = 3) -> list[dict]`, `scenario_from_text(description: str) -> str`, `explain_failure(fixture: dict, model_sql: str, diff: dict) -> str` — all raise `NotImplementedError` unconditionally. No other task depends on this one; it exists purely to fix the Phase-1+ package shape now (spec §2) so later phases are additive.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai_stubs.py
import pytest

from specdbt.ai.stubs import LLMClient, explain_failure, generate_fixtures, scenario_from_text


def test_llm_client_complete_not_implemented():
    with pytest.raises(NotImplementedError):
        LLMClient().complete("hello")


def test_generate_fixtures_not_implemented():
    with pytest.raises(NotImplementedError):
        generate_fixtures("select 1", {"a": "int"})


def test_scenario_from_text_not_implemented():
    with pytest.raises(NotImplementedError):
        scenario_from_text("a scenario description")


def test_explain_failure_not_implemented():
    with pytest.raises(NotImplementedError):
        explain_failure({}, "select 1", {})
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_ai_stubs.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.ai.stubs'`.

- [ ] **Step 3: Implement**

```python
# src/specdbt/ai/stubs.py
"""Typed placeholders for the AI layer (Phase 3 -- see the original plan set's
03-ai-integration-plan.md). Nothing here executes; this only fixes the package
shape from the Phase 0 spec (§2) so Phase 3 is additive, not a restructure."""

from __future__ import annotations

_NOT_YET = "AI features ship in Phase 3 -- see the roadmap doc."


class LLMClient:
    """Placeholder for the provider-agnostic LLM client (Phase 3)."""

    def complete(self, prompt: str) -> str:
        raise NotImplementedError(_NOT_YET)


def generate_fixtures(model_sql: str, schema: dict[str, str], count: int = 3) -> list[dict]:
    """Fixture synthesis (Phase 3, 03-ai-integration-plan.md §1)."""
    raise NotImplementedError(_NOT_YET)


def scenario_from_text(description: str) -> str:
    """Natural-language -> Gherkin (Phase 3, 03-ai-integration-plan.md §2)."""
    raise NotImplementedError(_NOT_YET)


def explain_failure(fixture: dict, model_sql: str, diff: dict) -> str:
    """Failure triage (Phase 3, 03-ai-integration-plan.md §4)."""
    raise NotImplementedError(_NOT_YET)
```

- [ ] **Step 4: Run and confirm pass**

```bash
uv run pytest tests/test_ai_stubs.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/ai/stubs.py tests/test_ai_stubs.py
git commit -m "chore: scaffold AI layer stubs for Phase 3

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 12: Real data-pulse example scenarios + README (Definition of Done)

**Files:**
- Create: 5 `.feature` files + 5 `.canned.py` files under `examples/data_pulse/features/`
- Create: `tests/test_examples_data_pulse.py`
- Modify: `README.md` (replace the Task 1 stub)

**Interfaces:**
- Consumes: `cli` (Task 10) via `click.testing.CliRunner`, for the integration test.
- Produces: nothing new — this task is the dogfood/integration task that proves the whole Phase 0 pipeline (Tasks 2–10) against real model shapes pulled from `~/dev/data-pulse/transforms/models/` on 2026-08-23 (spec §5). No dependency on the data-pulse repo at runtime — these are standalone `.feature`/`.canned.py` files.

- [ ] **Step 1: Write `examples/data_pulse/features/silver_weather_drops_null_timestamp.feature`**

```gherkin
Feature: Silver weather standardization

  Scenario: A row with a missing timestamp is dropped
    Given the following rows in "bronze_weather":
      | timestamp           | temperature | wind_speed | wind_direction | precipitation | cloud_cover | condition | source_id |
      | 2026-08-18 06:00:00 | 18.2        | 12.4       | 220             | 0.0            | 40          | Clear     | brightsky |
      |                     | 19.0        | 10.0       | 200             | 0.0            | 30          | Clear     | brightsky |
    When the "silver_weather" model runs
    Then "silver_weather" should have 1 row
    And the row for source_id "brightsky" should have temperature_c 18.2
```

This targets `~/dev/data-pulse/transforms/models/silver/silver_weather.sql`'s `WHERE timestamp IS NOT NULL` clause — the second row (no timestamp) must not survive.

- [ ] **Step 2: Write `examples/data_pulse/features/silver_weather_drops_null_timestamp.canned.py`**

```python
"""Hand-computed from silver_weather.sql: the null-timestamp row is filtered by
WHERE timestamp IS NOT NULL; the remaining row is cast per the SELECT list."""

from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "silver_weather": ExecutionResult.of(
        rows=[
            {
                "timestamp": "2026-08-18 06:00:00",
                "hour": "2026-08-18 06:00:00",
                "date": "2026-08-18",
                "temperature_c": 18.2,
                "wind_speed_kmh": 12.4,
                "wind_direction_deg": 220,
                "precipitation_mm": 0.0,
                "cloud_cover_pct": 40,
                "condition": "clear",
                "source_id": "brightsky",
            }
        ],
    ),
}
```

- [ ] **Step 3: Write `examples/data_pulse/features/silver_weather_casts_and_normalizes.feature`**

```gherkin
Feature: Silver weather standardization

  Scenario: A reading is cast and its condition text is lowercased
    Given the following rows in "bronze_weather":
      | timestamp           | temperature | wind_speed | wind_direction | precipitation | cloud_cover | condition | source_id  |
      | 2026-08-18 07:00:00 | 21.6        | 8.3        | 190             | 2.5            | 75          | RAIN      | dwd_backup |
    When the "silver_weather" model runs
    Then "silver_weather" should have 1 row
    And the row for source_id "dwd_backup" should have condition "rain"
```

Targets the `LOWER(TRIM(condition))` cast in `silver_weather.sql`.

- [ ] **Step 4: Write `examples/data_pulse/features/silver_weather_casts_and_normalizes.canned.py`**

```python
"""Hand-computed from silver_weather.sql: LOWER(TRIM(condition)) turns
'RAIN' into 'rain'; all other columns are straight casts of the input."""

from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "silver_weather": ExecutionResult.of(
        rows=[
            {
                "timestamp": "2026-08-18 07:00:00",
                "hour": "2026-08-18 07:00:00",
                "date": "2026-08-18",
                "temperature_c": 21.6,
                "wind_speed_kmh": 8.3,
                "wind_direction_deg": 190,
                "precipitation_mm": 2.5,
                "cloud_cover_pct": 75,
                "condition": "rain",
                "source_id": "dwd_backup",
            }
        ],
    ),
}
```

- [ ] **Step 5: Write `examples/data_pulse/features/gold_weather_daily_aggregates_by_date.feature`**

```gherkin
Feature: Gold daily weather aggregation

  Scenario: Two hourly readings on the same date aggregate into one daily row
    Given the following rows in "silver_weather":
      | date       | temperature_c | wind_speed_kmh | precipitation_mm | cloud_cover_pct |
      | 2026-08-18 | 16.0           | 10.0            | 0.0               | 20               |
      | 2026-08-18 | 20.0           | 14.0            | 1.0               | 60               |
    When the "gold_weather_daily" model runs
    Then "gold_weather_daily" should have 1 row
    And the row for date "2026-08-18" should have avg_temp_c 18.0
    And the row for date "2026-08-18" should have hour_count 2
```

Targets the `GROUP BY date` aggregation in `gold_weather_daily.sql`.

- [ ] **Step 6: Write `examples/data_pulse/features/gold_weather_daily_aggregates_by_date.canned.py`**

```python
"""Hand-computed from gold_weather_daily.sql for two hourly rows on the same
date: avg_temp_c = (16.0 + 20.0) / 2 = 18.0, hour_count = 2, etc."""

from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "gold_weather_daily": ExecutionResult.of(
        rows=[
            {
                "date": "2026-08-18",
                "avg_temp_c": 18.0,
                "max_temp_c": 20.0,
                "min_temp_c": 16.0,
                "avg_wind_speed_kmh": 12.0,
                "max_wind_speed_kmh": 14.0,
                "total_precipitation_mm": 1.0,
                "avg_cloud_cover_pct": 40.0,
                "hour_count": 2,
            }
        ],
    ),
}
```

- [ ] **Step 7: Write `examples/data_pulse/features/gold_weather_anomalies_flags_outlier.feature`**

```gherkin
Feature: Gold weather anomaly detection

  Scenario: A sharp spike relative to the rolling baseline is flagged as an anomaly
    Given the following rows in "gold_weather_daily":
      | date       | avg_temp_c |
      | 2026-07-20 | 18.0       |
      | 2026-07-21 | 17.5       |
      | 2026-07-22 | 18.2       |
      | 2026-08-18 | 32.0       |
    When the "gold_weather_anomalies" model runs
    Then "gold_weather_anomalies" should have 1 row
    And the row for date "2026-08-18" should have is_anomaly True
    And the row for date "2026-08-18" should have z_score 14.0
```

Targets the `is_anomaly` `CASE WHEN` branch (`|z_score| > 2`) in `gold_weather_anomalies.sql`.

- [ ] **Step 8: Write `examples/data_pulse/features/gold_weather_anomalies_flags_outlier.canned.py`**

```python
"""Hand-computed from gold_weather_anomalies.sql's real formula, given an
as-if-already-computed rolling_avg=18.0 and rolling_stddev=1.0 for the target
date (representing a stable ~18C baseline over the trailing window):
z_score = (avg_temp_c - rolling_avg) / rolling_stddev = (32.0 - 18.0) / 1.0 = 14.0
is_anomaly = rolling_stddev > 0 AND abs(z_score) > 2  ->  True."""

from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "gold_weather_anomalies": ExecutionResult.of(
        rows=[
            {
                "date": "2026-08-18",
                "avg_temp_c": 32.0,
                "rolling_avg": 18.0,
                "rolling_stddev": 1.0,
                "z_score": 14.0,
                "is_anomaly": True,
            }
        ],
    ),
}
```

- [ ] **Step 9: Write `examples/data_pulse/features/gold_weather_anomalies_normal_reading.feature`**

```gherkin
Feature: Gold weather anomaly detection

  Scenario: A reading close to the rolling baseline is not flagged
    Given the following rows in "gold_weather_daily":
      | date       | avg_temp_c |
      | 2026-07-21 | 17.8       |
      | 2026-07-22 | 18.1       |
      | 2026-08-19 | 18.5       |
    When the "gold_weather_anomalies" model runs
    Then "gold_weather_anomalies" should have 1 row
    And the row for date "2026-08-19" should have is_anomaly False
    And the row for date "2026-08-19" should have z_score 0.5
```

Covers the other branch of the same `CASE WHEN` that Step 7/8 covers — this is exactly the "untested branch" problem named in `00-overview-and-vision.md` §1.3.

- [ ] **Step 10: Write `examples/data_pulse/features/gold_weather_anomalies_normal_reading.canned.py`**

```python
"""Hand-computed the same way as the outlier scenario, with a small deviation:
rolling_avg=18.0, rolling_stddev=1.0, avg_temp_c=18.5 ->
z_score = (18.5 - 18.0) / 1.0 = 0.5  ->  |0.5| is not > 2  ->  is_anomaly = False."""

from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "gold_weather_anomalies": ExecutionResult.of(
        rows=[
            {
                "date": "2026-08-19",
                "avg_temp_c": 18.5,
                "rolling_avg": 18.0,
                "rolling_stddev": 1.0,
                "z_score": 0.5,
                "is_anomaly": False,
            }
        ],
    ),
}
```

- [ ] **Step 11: Write the failing integration test**

```python
# tests/test_examples_data_pulse.py
from pathlib import Path

from click.testing import CliRunner

from specdbt.cli import cli

EXAMPLES_DIR = Path(__file__).parent.parent / "examples" / "data_pulse" / "features"


def test_all_data_pulse_examples_pass():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", str(EXAMPLES_DIR)])
    assert result.exit_code == 0, result.output
    assert "5 scenario(s)" in result.output
    assert "0 failure(s)" in result.output
```

- [ ] **Step 12: Run and confirm it fails before the files above exist / confirm it passes after**

```bash
uv run pytest tests/test_examples_data_pulse.py -v
```

Run this once the 5 `.feature`/`.canned.py` pairs from Steps 1–10 are in place — expected: 1 passed (this task, unlike Tasks 2–11, writes its test after its fixtures since the fixtures ARE the thing under test; there's no meaningful red state to check here beyond "file not found" if a step above is skipped).

- [ ] **Step 13: Manually verify the CLI output matches the spec's Definition of Done**

```bash
uv run specdbt run examples/data_pulse/features
```

Expected: 5 `Feature:` blocks, all steps marked `✓`, ending in `5 scenario(s), <N> step(s), 0 failure(s)`.

- [ ] **Step 14: Write the final `README.md`**

```markdown
# specdbt

BDD-style `Given`/`When`/`Then` testing for dbt models. Write scenarios a
stakeholder can read, get a fast structural check today and a real-SQL
correctness guarantee once Phase 1 lands.

**Status: Phase 0** — the parser → fixture → adapter → assertion → report
pipeline works end to end against a `FakeAdapter` (hardcoded rows, no real
SQL/Polars execution yet). See `docs/superpowers/specs/2026-08-23-specdbt-phase0-design.md`
for what's in and out of scope, and `docs/superpowers/plans/2026-08-23-specdbt-phase0.md`
for how it was built.

## Quickstart

```bash
uv sync
uv run specdbt init features/       # scaffold an example .feature + its canned result
uv run specdbt run features/        # parse, run, report
```

## Try it against real models

`examples/data_pulse/features/` has 5 scenarios written against real models
from a live dbt project (`~/dev/data-pulse`), including both branches of a
`CASE WHEN` in an anomaly-detection model:

```bash
uv run specdbt run examples/data_pulse/features
```

## How a scenario looks

```gherkin
Feature: Silver weather standardization

  Scenario: A row with a missing timestamp is dropped
    Given the following rows in "bronze_weather":
      | timestamp           | temperature | ... |
      | 2026-08-18 06:00:00 | 18.2        | ... |
      |                     | 19.0        | ... |
    When the "silver_weather" model runs
    Then "silver_weather" should have 1 row
```

Each `.feature` file may have a co-located `.canned.py` file exposing
`CANNED_RESULTS: dict[str, ExecutionResult]` — Phase 0's `FakeAdapter` returns
these hardcoded rows rather than computing anything, to prove the pipeline
plumbing before a real execution engine exists (Phase 1: `PolarsAdapter` /
`DuckDBAdapter`).

## Development

```bash
uv run pytest       # test suite
uv run ruff check .
uv run ruff format .
```

## Roadmap

Phase 0 (this): skeleton pipeline, `FakeAdapter`, CLI, dogfooded on real models.
Phase 1: real `PolarsAdapter`/`DuckDBAdapter`, `--parity` mode. Phase 2: compile
scenarios to native dbt `unit_tests:` YAML. Phase 3: AI-assisted fixture
synthesis, NL→Gherkin, failure triage (stubs already scaffolded in `src/specdbt/ai/`).

## License

MIT — see `LICENSE`.
```

- [ ] **Step 15: Run the full test suite and lint**

```bash
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Expected: all tests pass, `ruff check` reports no issues, `ruff format --check` reports no files would be reformatted (if it does, run `uv run ruff format .` and re-check). If `ruff check` reports import-order (`I001`) issues, run `uv run ruff check --fix .` and re-verify — the import blocks in this plan were checked against ruff's default isort behavior but not against this exact project's first-party detection.

- [ ] **Step 16: Commit**

```bash
git add examples README.md tests/test_examples_data_pulse.py
git commit -m "feat: dogfood specdbt on real data-pulse models

5 scenarios across silver_weather, gold_weather_daily, and
gold_weather_anomalies (both CASE WHEN branches) -- satisfies the
Phase 0 Definition of Done from the spec.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Definition of Done

- `uv run pytest` passes, all Tasks 2–12 covered.
- `uv run ruff check .` and `uv run ruff format --check .` clean.
- `uv run specdbt run examples/data_pulse/features` prints 5 passing scenarios, 0 failures.
- 12 local commits, nothing pushed anywhere.
- `docs/superpowers/specs/2026-08-23-specdbt-phase0-design.md` and this plan are both in the repo, committed.
