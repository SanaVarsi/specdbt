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
