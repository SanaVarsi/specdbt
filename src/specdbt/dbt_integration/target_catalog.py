"""Resolves the target's configured catalog/database once per run, so
schema DDL, fixture CTAS, and ref()/source() substitution all address the
same namespace (spec: macro-tier adapter-dispatch design, 2026-08-30).

Reads the *raw*, Jinja-rendered profile target dict via dbt-core's own
Profile.render_profile -- not a parsed Credentials dataclass -- because
some adapters' Credentials default this field to a non-None value
(dbt-duckdb's Credentials.database defaults to "main"), which would
silently turn every DuckDB relation 3-part. Working off the raw dict means
"no catalog/database key in the YAML" resolves to None by construction,
not by an adapter-type special case.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dbt.config.profile import Profile, read_profile
from dbt.config.renderer import ProfileRenderer
from dbt_common.context import set_invocation_context


def resolve_target_catalog(project_dir: Path, profiles_dir: Path, target: str | None) -> str | None:
    dbt_project = yaml.safe_load((Path(project_dir) / "dbt_project.yml").read_text())
    profile_name = dbt_project["profile"]
    raw_profiles = read_profile(str(profiles_dir))
    raw_profile = raw_profiles[profile_name]
    renderer = ProfileRenderer({})
    set_invocation_context(os.environ)
    _target_name, profile_data = Profile.render_profile(raw_profile, profile_name, target, renderer)
    return profile_data.get("catalog") or profile_data.get("database") or profile_data.get("dbname")
