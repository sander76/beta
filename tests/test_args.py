import argparse

import pytest
from clipstick import parse
from clipstick.__intermediary import ArgsModel
from clipstick.args import to_argparse, to_snake
from pydantic import BaseModel


@pytest.mark.parametrize(
    "input,result",
    [
        ("MyCasedValue", "my_cased_value"),
        ("myCasedValue", "my_cased_value"),
        ("Value", "value"),
    ],
)
def test_to_snake(input, result):
    value = to_snake(input)

    assert value == result
