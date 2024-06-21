from typing import Annotated

import pytest
from clipstick import short
from clipstick._clipstick import parse
from pydantic import BaseModel


def test_list_args_success(models):
    model = parse(models.CollectionModel, ["--my-list", "10", "--my-list", "11"])

    assert model == models.CollectionModel(my_list=[10, 11])


def test_list_short_args_success(models):
    model = parse(models.CollectionModel, ["-m", "10", "-m", "11"])

    assert model == models.CollectionModel(my_list=[10, 11])


def test_list_short_and_long_args_success(models):
    model = parse(models.CollectionModel, ["--my-list", "10", "-m", "11"])

    assert model == models.CollectionModel(my_list=[10, 11])


# def test_invalid_list_item_raises(capture_output):
#     with pytest.raises(SystemExit) as err:
#         capture_output(MyModel, ["--my-list", "10", "--my-list", "eleven"])
#     assert err.value.code != 0
#     assert (
#         """ERROR:
# Incorrect value for --my-list ('eleven'). Input should be a valid integer, unable to parse string as an integer
# """
#         == capture_output.captured_output
#     )


# def test_help(capture_output):
#     with pytest.raises(SystemExit) as err:
#         capture_output(MyModel, ["-h"])

#     assert err.value.code == 0
#     assert (
#         """
# Usage: my-cli-app [Options]

# Options:
#     -m --my-list         A list type object Can be applied multiple times. [list[int]] [default = [9]]
# """
#         == capture_output.captured_output
#     )
