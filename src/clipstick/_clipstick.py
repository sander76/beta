import dataclasses
import sys
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, is_dataclass
from typing import Final

from pydantic import BaseModel

from clipstick import _help
from clipstick.__intermediary import ArgsModel, materialize
from clipstick._exceptions import ClipStickError
from clipstick._parse import validate_model
from clipstick._tokens import TPydanticModel
from clipstick.args import to_argparse

DUMMY_ENTRY_POINT: Final[str] = "my-cli-app"


def parse(model: type[TPydanticModel], args: list[str] | None = None) -> TPydanticModel:
    """Create an instance of the provided model.

    Leave `args` to None in production. Only use it for testing.

    Args:
        model: The pydantic class we want to populate.
        args: The list of arguments. This is useful for testing.
            Provide a list and check if your model is parsed correctly.
            If not provided clipstick will evaluate the arguments from `sys.argv`.

    Returns:
        An instance of the pydantic class we provided as argument populated with the provided args.
    """
    try:
        validate_model(model)
    except ClipStickError as err:
        _help.error(err)
        sys.exit(1)
    if args is None:
        entry_point, args = sys.argv[0], sys.argv[1:]
    else:
        # Normally the first item in your sys.argv is the command/entrypoint you've entered.
        # During testing you don't provide that (only the actual arguments you enter after that).
        entry_point = DUMMY_ENTRY_POINT

    if issubclass(model, BaseModel):
        args_model = ArgsModel.from_pydantic(model)
    elif dataclasses.is_dataclass(model):
        args_model = ArgsModel.from_dataclass(model)
    else:
        _help.error("invalid model")
        sys.exit(3)
    my_ns = Namespace(__clipstick_target=model)
    arg_parser = to_argparse(args_model)

    ns = arg_parser.parse_args(args, namespace=my_ns)

    return materialize(ns)
