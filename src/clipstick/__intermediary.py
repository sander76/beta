import dataclasses
import inspect
from argparse import Namespace
from dataclasses import dataclass
from enum import Enum
from typing import Any, get_args

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from clipstick._docstring import docstring_from_dataclass, docstring_from_pydantic_model
from clipstick._exceptions import InvalidTypesInUnion


# For passing "undefined or none" values to and from widgets and forms, we
# will be using the NO_VALUE sentinel instead of `None`:
# In some cases `None` can be a valid value instead of a passing sentinel.
# For this reason and to avoid confusion NO_VALUE will be used everywhere.
class NOTHING(Enum):
    """A nothing enum.

    An implementation for a Sentinel value for NO_VALUE as suggested here:
    https://peps.python.org/pep-0484/#support-for-singleton-types-in-unions
    """

    token = 0


NO_VALUE: NOTHING = NOTHING.token


def _is_pydantic_subcommand(annotation: type):
    args = get_args(annotation)
    if not all((inspect.isclass(arg) for arg in args)):
        return False
    if not any(issubclass(arg, BaseModel) for arg in args):
        return False

    if not all(issubclass(arg, BaseModel) for arg in args):
        raise InvalidTypesInUnion()
    return True


def _is_dataclass_subcommand(annotation: type) -> bool:
    args = get_args(annotation)
    if all((dataclasses.is_dataclass(arg) for arg in args)):
        return True
    if any((dataclasses.is_dataclass(arg) for arg in args)):
        raise InvalidTypesInUnion
    return False


@dataclass
class Arg:
    key: str
    default_value: Any

    help: str | None
    type: type[object]
    is_sub_command: bool

    @property
    def required(self):
        if self.default_value is NO_VALUE:
            return True
        return False

    @property
    def argument(self):
        return self.key.replace("_", "-")


class ArgsModel:
    def __init__(self, args: list[Arg], model: type) -> None:
        self.model_name = model
        self.args: list[Arg] = args

    @classmethod
    def from_pydantic(cls, model: type[BaseModel]) -> "ArgsModel":
        args: list[Arg] = []
        docstring_from_pydantic_model(model)
        for key, field_info in model.model_fields.items():
            sub_command = False
            if _is_pydantic_subcommand(field_info.annotation):
                sub_command = True
                _type = []
                for sub in get_args(field_info.annotation):
                    _type.append(ArgsModel.from_pydantic(sub))

            else:
                _type = field_info.annotation

            default_value = field_info.default
            if default_value is PydanticUndefined:
                default_value = NO_VALUE

            assert _type is not None
            args.append(
                Arg(
                    key=key,
                    default_value=default_value,
                    type=_type,
                    help=field_info.description,
                    is_sub_command=sub_command,
                )
            )
        return cls(args, model)

    @classmethod
    def from_dataclass(cls, model: type[dataclass]) -> "ArgsModel":
        docstring_from_dataclass(model)

        # Somehow it is not possible to access this property using dot notation.
        # it seems the wrapping inside this classmethod mangles the property name
        # to "_ArgsModel__clipstick_docstring."
        doc_strings = getattr(model, "__clipstick_docstring")
        members = {mbr[0]: mbr[1] for mbr in inspect.getmembers(model)}

        args: list[Arg] = []
        for key, value in model.__annotations__.items():
            sub_command = False
            if _is_dataclass_subcommand(value):
                sub_command = True
                _type = []
                for sub in get_args(value):
                    _type.append(ArgsModel.from_dataclass(sub))
            else:
                _type = value
            default_value = members.get(key, NO_VALUE)
            args.append(
                Arg(
                    key=key,
                    default_value=default_value,
                    type=_type,
                    help=doc_strings[key],
                    is_sub_command=sub_command,
                )
            )

        return cls(args, model)


def materialize(ns: Namespace) -> object:
    # materialize from the outer most leaf to the start model.

    # check if there is a namespace value amongst the keys.
    # if so, enter it and do the check again.

    for key in ns.__dict__:
        value = ns.__dict__[key]
        if isinstance(value, Namespace):
            ns.__dict__[key] = materialize(value)
    return ns.__dict__.pop("__clipstick_target")(**ns.__dict__)
