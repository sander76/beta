from textwrap import dedent
from typing import Annotated, Optional, Union

import pytest
from clipstick._annotations import short
from clipstick._clipstick import parse
from pydantic import BaseModel


def test_no_optionals(models):
    model = parse(models.OptionalsModel, [])
    assert model == models.OptionalsModel()


def test_positional(models, capsys):
    with pytest.raises(SystemExit) as err:
        parse(models.OptionalsModel, ["20"])

    out, err = capsys.readouterr()
    assert (
        err
        == """usage: run_pytest_script.py [-h] [--value-1 VALUE_1] [--value-2 VALUE_2]
run_pytest_script.py: error: unrecognized arguments: 20
"""
    )


def test_some_optionals(models):
    model = parse(models.OptionalsModel, ["--value-1", "24"])
    assert model == models.OptionalsModel(value_1=24)


def test_all_optionals(models):
    model = parse(models.OptionalsModel, ["--value-1", "24", "--value-2", "25"])
    assert model == models.OptionalsModel(value_1=24, value_2="25")


@pytest.mark.parametrize("args", [["--value-1", "12"], ["-v", "12"]])
def test_optional_with_short(args, models):
    model = parse(models.OptionalWithShort, args)
    assert model == models.OptionalWithShort(value_1=12)


def test_optional_value_old_typing(models):
    model = parse(models.OptionalValueNoneOptional, ["--value-1", "10"])
    assert model == models.OptionalValueNoneOptional(value_1=10)


def test_optional_value_new_typing(models):
    model = parse(models.OptionalValueNonePipe, ["--value-1", "10"])
    assert model == models.OptionalValueNonePipe(value_1=10)


# def test_help(capture_output):
#     with pytest.raises(SystemExit) as err:
#         capture_output(OptionalsModel, ["-h"])

#     assert err.value.code == 0
#     assert """
# Usage: my-cli-app [Options]

# A model with only optionals.

# Options:
#     --value-1            Optional value 1. [int] [default = 10]
#     --value-2             [str] [default = ABC]
# """


# def test_help_with_shorts(capture_output):
#     with pytest.raises(SystemExit) as err:
#         capture_output(OptionalWithShort, ["-h"])

#     assert err.value.code == 0
#     assert "-v --value-1" in capture_output.captured_output


# @pytest.mark.parametrize(
#     "model", [OptionalValueNonePipe, OptionalValueNoneOptional, OptionalValueNoneUnion]
# )
# def test_help_union_none(model, capture_output):
#     with pytest.raises(SystemExit) as err:
#         capture_output(model, ["-h"])

#     assert err.value.code == 0
#     assert (
#         """
# Usage: my-cli-app [Options]

# Options:
#     --value-1             [int] [default = None]
# """
#         == capture_output.captured_output
#     )
