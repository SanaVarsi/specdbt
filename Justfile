# One-command local dev setup. Install `just` first:
#   macOS:  brew install just
#   other:  https://github.com/casey/just#installation
# Then: `just setup` once, `just` (no args) to list targets.

default:
    @just --list

# Bootstrap everything needed to develop: python deps, git hooks.
setup:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v uv >/dev/null 2>&1 || {
        echo "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    }
    uv sync
    uv run pre-commit install
    echo "Setup done. Try: just test"

# Check for tools this repo uses and print an install hint for anything missing.
doctor:
    #!/usr/bin/env bash
    set -euo pipefail
    ok=1
    check() {
        if command -v "$1" >/dev/null 2>&1; then
            echo "  ok    $1"
        else
            echo "  MISSING  $1  -- $2"
            ok=0
        fi
    }
    check uv     "curl -LsSf https://astral.sh/uv/install.sh | sh"
    check docker "https://docs.docker.com/get-docker/  (only needed for 'just postgres-up')"
    [ "$ok" = 1 ] && echo "All required tools present." || { echo "Fix the above, then re-run 'just doctor'."; exit 1; }

# Full test suite -- DuckDB only, no external services required.
test:
    uv run pytest

# Scaffold DIR with an example .feature file + canned result (default: features/).
init dir="features":
    uv run specdbt init {{dir}}

# Run .feature files under TARGET (--engine fake by default); ARGS pass through to `specdbt run`.
run target="features" *args:
    uv run specdbt run {{target}} {{args}}

# Run the bundled jaffle_shop example against real dbt+DuckDB (both tiers).
run-example:
    #!/usr/bin/env bash
    set -euo pipefail
    (cd examples/jaffle_shop && uv run dbt deps --profiles-dir profiles)
    uv run specdbt run examples/jaffle_shop/features \
        --engine dbt \
        --project-dir examples/jaffle_shop \
        --profiles-dir examples/jaffle_shop/profiles

# Start local Postgres in Docker for the adapter test (generates .env on first run).
postgres-up:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v docker >/dev/null 2>&1 || {
        echo "docker not found. Install: https://docs.docker.com/get-docker/"
        exit 1
    }
    if [ ! -f .env ]; then
        generated="$(openssl rand -hex 12)"
        {
            echo "POSTGRES_USER=specdbt"
            printf 'POSTGRES_%s=%s\n' "PASSWORD" "$generated"
            echo "POSTGRES_DB=specdbt_test"
        } > .env
        echo "Wrote .env with a freshly generated local-only credential (gitignored)."
    fi
    docker compose up -d postgres
    echo "Postgres is up on localhost:5432. Next: just test-postgres"

# Run the Postgres adapter test against the container from 'postgres-up'.
test-postgres:
    #!/usr/bin/env bash
    set -euo pipefail
    [ -f .env ] || { echo "No .env found -- run 'just postgres-up' first."; exit 1; }
    set -a; source .env; set +a
    export SPECDBT_PG_USER="$POSTGRES_USER"
    export SPECDBT_PG_SECRET="$POSTGRES_PASSWORD"
    export SPECDBT_PG_DBNAME="$POSTGRES_DB"
    export SPECDBT_PG_HOST=localhost SPECDBT_PG_PORT=5432 SPECDBT_TEST_POSTGRES=1
    uv run pytest tests/test_dbt_adapter_postgres.py -v
