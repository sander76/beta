from types import ModuleType

import pytest
from clipstick.__intermediary import ArgsModel
from clipstick._clipstick import parse
from pydantic import BaseModel

from tests.models import dataclass_models, pydantic_models


@pytest.mark.parametrize(
    "model", [dataclass_models.SimpleModel, pydantic_models.SimpleModel]
)
def test_parse_simple_positional_only(model):
    result = parse(model, ["Adam"])

    assert result == model(my_value="Adam")


def test_str_model_default(models):
    result = parse(models.StrModelDefault, [])
    assert result == models.StrModelDefault()


def test_str_model_default_with_value(models):
    result = parse(models.StrModelDefault, ["--my-value", "custom"])
    assert result == models.StrModelDefault(my_value="custom")


def test_parse_int_model(models):
    result = parse(models.IntModel, ["10"])
    assert result == models.IntModel(my_value=10)


def test_too_much_positionals_must_raise(models):
    with pytest.raises(SystemExit) as err:
        parse(models.SimpleModel, ["Adam", "Ondra"])

    assert err.value.code == 1


def test_int_model_help(capsys, models):
    with pytest.raises(SystemExit) as err:
        parse(models.IntModel, ["-h"])

    assert err.value.code == 0
    captured = capsys.readouterr().out
    print(captured)

    assert (
        captured
        == """usage: run_pytest_script.py [-h] my_value

positional arguments:
  my_value

options:
  -h, --help  show this help message and exit
"""
    )
