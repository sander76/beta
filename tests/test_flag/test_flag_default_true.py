import pytest
from clipstick._clipstick import parse
from pydantic import BaseModel


class FlagDefaultTrue(BaseModel):
    """A model with flag."""

    proceed: bool = True
    """Continue with this operation."""


def test_default_true():
    model = parse(FlagDefaultTrue, ["--no-proceed"])

    assert model == FlagDefaultTrue(proceed=False)


def test_help(capture_output):
    with pytest.raises(SystemExit) as err:
        capture_output(FlagDefaultTrue, ["-h"])

    assert err.value.code == 0
    assert (
        """
Usage: my-cli-app [Options]

A model with flag.

Options:
    --no-proceed         Continue with this operation. [bool] [default = True]
"""
        == capture_output.captured_output
    )
