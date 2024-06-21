import pytest
from clipstick._clipstick import parse
from pydantic import BaseModel


class MyModel(BaseModel):
    my_list: list[int]
    """A list type object"""


def test_list_args_success():
    model = parse(MyModel, ["10", "11"])

    assert model == MyModel(my_list=[10, 11])


def test_invalid_list_item_raises(capsys):
    with pytest.raises(SystemExit) as err:
        parse(MyModel, ["10", "eleven"])
    assert err.value.code != 0
    out, err = capsys.readouterr()
    assert (
        err
        == """usage: run_pytest_script.py [-h] my_list [my_list ...]
run_pytest_script.py: error: argument my_list: invalid int value: 'eleven'
"""
    )


# def test_help(capture_output):
#     with pytest.raises(SystemExit) as err:
#         capture_output(MyModel, ["-h"])

#     assert err.value.code == 0
#     assert (
#         """
# Usage: my-cli-app [Arguments]

# Arguments:
#     -m --my-list         A list type object Can be applied multiple times. [list[int]]
# """
#         == capture_output.captured_output
#     )
