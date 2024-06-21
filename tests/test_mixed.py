# from copy import copy

# import pytest
# from clipstick import parse
# from pydantic import BaseModel


# def add_random_arg(
#     optional_arg: tuple, optional_arg_as_dict: dict, can_be_ignored: bool = False
# ):
#     """Decorator to insert an optional argument in all possible positions inside an argument list.

#     Args:
#         optional_arg: The optional argument to insert.
#         optional_arg_as_dict: the optional argument as a dict representation.
#             Must be parseable by pydantic.
#     """

#     def _decorator(func):
#         def _wrapper(*args, **kwargs):
#             for result in func():
#                 args, dct = result
#                 if can_be_ignored:
#                     yield (args, dct)
#                 for pos in range(len(args) + 1):
#                     new_list = copy(args)
#                     new_list.insert(pos, optional_arg)
#                     new_dict = copy(dct)
#                     new_dict.update(optional_arg_as_dict)
#                     yield (new_list, new_dict)

#         return _wrapper

#     return _decorator


# @add_random_arg(("--optional-bool",), {"optional_bool": True}, can_be_ignored=True)
# @add_random_arg(("--items", "40"), {"items": ["30", "40"]})
# @add_random_arg(("--items", "30"), {"items": ["30", "40"]})
# @add_random_arg(("--optional-1", "opt2"), {"optional_1": "opt2"}, can_be_ignored=True)
# def args_generator():
#     # these are positional args.
#     # order cannot be changed. All others, (anything with a -- or - prefix) can be put anyhere
#     # before, after or inbetween these positional args.
#     args = ["10", "--required-bool"]
#     yield (
#         args,
#         {"pos_value_1": "10", "required_bool": True},
#     )


# def all_args_and_dict():
#     """A list of argument strings in any possible order which should
#     be consumable by clipstick."""
#     items = []
#     for args, dct in args_generator():
#         flattened_args = []
#         for arg in args:
#             if isinstance(arg, tuple):
#                 flattened_args.extend(arg)
#             else:
#                 flattened_args.append(arg)
#         items.append((flattened_args, dct))

#     return items


# @pytest.mark.parametrize("args,dct", all_args_and_dict())
# def test_mixed_model(args, dct):
#     model = parse(Main, args)
#     model.items = sorted(model.items)

#     expected_model = Main.model_validate(dct)
#     expected_model.items = sorted(expected_model.items)
#     assert model == expected_model


# class Main(BaseModel):
#     pos_value_1: int

#     required_bool: bool
#     items: list[int]

#     optional_1: str = "opt1"
#     optional_bool: bool = False


# def test_main_help(capture_output):
#     """Manually check the output at `help_output` folder."""
#     with pytest.raises(SystemExit) as err:
#         capture_output(Main, ["-h"])

#     assert err.value.code == 0
#     assert (
#         """
# Usage: my-cli-app [Arguments] [Options]

# Arguments:
#     pos-value-1           [int]
#     --required-bool/--no-required-bool  [bool]
#     --items               Can be applied multiple times. [list[int]]

# Options:
#     --optional-1          [str] [default = opt1]
#     --optional-bool       [bool] [default = False]
# """
#         == capture_output.captured_output
#     )
