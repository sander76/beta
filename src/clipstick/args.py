import argparse
import re
from argparse import Namespace, _SubParsersAction
from inspect import getargs
from typing import Any, Iterator, get_args

from pydantic import BaseModel

from clipstick import _parse as p
from clipstick import _tokens as t
from clipstick.__intermediary import ArgsModel
from clipstick._docstring import set_undefined_field_descriptions_from_var_docstrings
from clipstick._exceptions import OnlyOneTypeAllowedInCollection


def _is_collection_type(annotation: type) -> bool:
    if getattr(annotation, "__origin__", None) in (list, set):
        return True
    return False


class DatargsSubparsers(_SubParsersAction):
    """A subparsers action that creates a nested namespace structure."""

    def __init__(self, name, *args, **kwargs):
        self.__name = name
        super().__init__(*args, **kwargs)
        self._command_type_map = {}

    def add_parser(self, typ: type, name: str, aliases=(), *args, **kwargs):
        kwargs = kwargs | {"argument_default": argparse.SUPPRESS}
        result = super().add_parser(name, aliases=aliases, *args, **kwargs)
        for alias in [name, *aliases]:
            self._command_type_map[alias] = typ
        return result

    def __call__(self, parser, namespace, values, *args, **kwargs):
        name, *_ = values
        new_ns = Namespace(__clipstick_target=self._command_type_map[name])
        super().__call__(parser, new_ns, values)

        if hasattr(new_ns, self.dest):
            delattr(new_ns, self.dest)

        setattr(namespace, self.__name, new_ns)


def to_snake(camel: str) -> str:
    """Convert a PascalCase or camelCase string to snake_case.

    Args:
        camel: The string to convert.

    Returns:
        The converted string in snake_case.
    """
    snake = re.sub(r"([a-zA-Z])([0-9])", lambda m: f"{m.group(1)}_{m.group(2)}", camel)
    snake = re.sub(r"([a-z0-9])([A-Z])", lambda m: f"{m.group(1)}_{m.group(2)}", snake)
    return snake.lower()


def to_argparse(
    model: ArgsModel, parser: argparse.ArgumentParser | None = None
) -> argparse.ArgumentParser:
    if parser is None:
        parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
    for arg in model.args:
        _argument_kwargs = {"help": arg.help}
        if not arg.key == arg.argument:
            _argument_kwargs["dest"] = arg.key

        annotation = arg.type
        if arg.is_sub_command:
            sub_parsers = parser.add_subparsers(action=DatargsSubparsers, name=arg.key)
            for sub_args_model in annotation:
                parser_name = to_snake(str(sub_args_model.model_name.__name__))
                sub_parser = sub_parsers.add_parser(
                    sub_args_model.model_name, parser_name
                )
                to_argparse(sub_args_model, sub_parser)
            continue
        if t.is_union(annotation):
            annotation = t.one_from_union(get_args(annotation))
        if _is_collection_type(annotation):
            _collection_types = get_args(get_args(annotation)[0])
            if len(_collection_types) > 1:
                raise OnlyOneTypeAllowedInCollection(arg)
            if _collection_types is not Any:
                _argument_kwargs["type"] = _type_args[0]

            if arg.required:
                _argument_kwargs["nargs"] = "+"
            else:
                _argument_kwargs["action"] = "append"

            parser.add_argument(arg.argument, **_argument_kwargs)

        elif p._is_boolean_type(annotation):
            parser.add_argument(
                f"--{arg.argument}",
                action=argparse.BooleanOptionalAction,
                dest=arg.key,
                required=arg.required,
            )

        elif p._is_choice(annotation):
            choices = get_args(annotation)

            if arg.required:
                parser.add_argument(arg.key, choices=choices)
            else:
                parser.add_argument(
                    f"--{arg.key}", default=arg.default_value, choices=choices
                )

        else:
            if arg.required:
                parser.add_argument(arg.key, type=annotation)
            else:
                parser.add_argument(f"--{arg.argument}", dest=arg.key, type=annotation)

    return parser
