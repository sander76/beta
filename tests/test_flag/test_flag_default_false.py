import pytest
from clipstick._clipstick import parse
from pydantic import BaseModel

from tests.models import dataclass_models, pydantic_models


@pytest.mark.parametrize(
    "model", [pydantic_models.FlagDefaultFalse, dataclass_models.FlagDefaultFalse]
)
def test_default_false_model(model):
    result = parse(model, ["--proceed"])

    assert result == model(proceed=True)


@pytest.mark.parametrize(
    "model", [pydantic_models.FlagDefaultFalse, dataclass_models.FlagDefaultFalse]
)
def test_default_false_model_no_args(model):
    result = parse(model, [])

    assert result == model()


def test_help(capture_output):
    with pytest.raises(SystemExit) as err:
        capture_output(FlagDefaultFalse, ["-h"])

    assert err.value.code == 0
    assert (
        """
Usage: my-cli-app [Options]

A model with flag.

Options:
    --proceed            continue with this operation. [bool] [default = False]
"""
        == capture_output.captured_output
    )
