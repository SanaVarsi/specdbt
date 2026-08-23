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
