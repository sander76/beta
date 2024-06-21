from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import cached_property
from types import NoneType, UnionType
from typing import (
    Final,
    Generic,
    TypedDict,
    TypeVar,
    get_args,
)

from pydantic import BaseModel, ValidationError
from pydantic.alias_generators import to_snake
from pydantic.fields import FieldInfo

from clipstick import _exceptions, _help
from clipstick._annotations import Short

TPydanticModel = TypeVar("TPydanticModel")
_HELP_KEYS = ("-h", "--help")


class THelp(TypedDict):
    """Help data for help output.

    Data is different per token.
    """

    arguments: str
    description: str
    type: str
    default: str


def _to_false_key(field: str) -> str:
    return f"--no-{field.replace('_','-')}"


def _to_key(field: str) -> str:
    return f"--{field.replace('_','-')}"


def _to_short(field: str) -> str:
    return f"-{field}"


def _to_false_short(field: str) -> str:
    return f"-no-{field}"


def is_union(annotation: type) -> bool:
    """Check whether the annotation is of a union type.

    Checks for both old style union (`:Union[str,None]`) and new style unions (`:str|None`)
    Also the `:Optional[str]` type is considered a union (which it just is.)
    """
    _name = getattr(annotation, "__name__", None)

    if _name in ("Optional", "Union") or isinstance(annotation, UnionType):
        return True
    return False


def one_from_union(args: tuple[type]) -> type:
    """Return the type of a union which is not the NoneType.

    Clipstick allows Unions (or Optionals) when it is a Union between a
    type and None. We check and return the not None type for further processing.

    Args:
        args: The arguments of the Union type.
            Most likely received from the get_args call from the typing module.

    Returns:
        the not-None annotation.

    Raises:
        InvalidUnion: when not a union of two where one is None.
    """
    without_none = tuple((arg for arg in args if arg is not NoneType))

    if len(without_none) == 1:
        return without_none[0]
    raise _exceptions.InvalidUnion()


class Positional:
    """Positional/required argument token.

    A token is generated based on the pydantic field definition and used
    for matching and parsing a provided list of arguments.
    """

    required: Final[bool] = True

    def __init__(self, field: str, field_info: FieldInfo):
        """Init.

        Args:
            field: field name as defined in the class (a class attribute)
            field_info: Pydantic fieldinfo
        """
        self.field = field
        self.field_info = field_info
        # In case of an error we want to know which keyword was used (like --proceed or -p etc.)
        # We store what used argument here.
        self.used_arg: str = field.replace("_", "-")
        self._match: dict[str, str] | None = None

    @cached_property
    def user_keys(self) -> list[str]:
        """Argument keys (like --verbose or --value) provided by a user to indicate a keyword or flag.

        Many times this is a list of normalized model fields or provided shorthand names.
        """
        return [(self.field.replace("_", "-"))]

    def match(self, idx: int, arguments: list[str]) -> tuple[bool, int]:
        """Check if this token is a match given the list of arguments."""
        if arguments[idx].startswith("-"):
            return False, idx
        if self._match:
            # this token was already a match.
            return False, idx
        self._match = {self.field: arguments[idx]}
        return True, idx + 1

    def parse(self) -> dict[str, str]:
        """Return the token data in a parseable way.

        This mean returning a (partial) dict with a key, value pair
        which is to be consumed by pydantic.
        """
        return self._match if self._match else {}

    def help(self) -> THelp:
        """Help data based on field information.

        Returns:
            Help information. To be processed for further output
        """
        return {
            "arguments": "/".join(self.user_keys),
            "description": self.field_info.description or "",
            "type": self.field_info.annotation.__name__
            if self.field_info.annotation
            else "",
            "default": "",
        }


class Optional:
    """Optional/keyworded argument token.

    A token is generated based on the pydantic field definition and used
    for matching and parsing a provided list of arguments.
    """

    required: Final[bool] = False

    def __init__(self, field: str, field_info: FieldInfo):
        """Init.

        Args:
            field: field name as defined in the class (a class attribute)
            field_info: Pydantic fieldinfo
        """
        self.field = field
        self.field_info = field_info

        # In case of an error we want to know which keyword was used (like --proceed or -p etc.)
        # We store what used argument here.
        self.used_arg: str = ""
        self._match: dict[str, str] = {}

    @cached_property
    def short_keys(self) -> list[str]:
        return [
            _to_short(short.short)
            for short in self.field_info.metadata
            if isinstance(short, Short)
        ]

    @cached_property
    def keys(self) -> list[str]:
        return [_to_key(self.field)]

    @cached_property
    def user_keys(self) -> list[str]:
        """Argument keys (like --verbose or --value) provided by a user to indicate a keyword or flag.

        Many times this is a list of normalized pydantic fields or provided shorthand names.
        """
        return self.keys + self.short_keys

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        try:
            if values[idx] not in self.user_keys:
                return False, idx
        except IndexError:
            return False, idx
        self.used_arg = values[idx]
        self._match[self.field] = values[idx + 1]

        return True, idx + 2

    def parse(self) -> dict[str, str]:
        """Return the token data in a parseable way.

        This mean returning a (partial) dict with a key, value pair
        which is to be consumed by pydantic.
        """
        return self._match

    def help(self) -> THelp:
        """Help data based on field information.

        Returns:
            Help information. To be processed for further output
        """
        assert self.field_info.annotation is not None

        if is_union(self.field_info.annotation):
            _type = (one_from_union(get_args(self.field_info.annotation))).__name__

        else:
            _type = self.field_info.annotation.__name__

        return {
            "arguments": (f'{"/".join(self.short_keys)} {"/".join(self.keys)}').strip(),
            "description": self.field_info.description or "",
            "type": _type,
            "default": f"default = {self.field_info.default}",
        }


def _allowed_values(annotation: object) -> str:
    return f"allowed values: {', '.join(str(arg) for arg in get_args(annotation))}"


class Choice(Positional):
    def help(self) -> THelp:
        """Help data based on field information.

        Returns:
            Help information. To be processed for further output
        """
        _help = super().help()
        _help["type"] = _allowed_values(self.field_info.annotation)
        return _help


class OptionalChoice(Optional):
    def help(self) -> THelp:
        """Help data based on field information.

        Returns:
            Help information. To be processed for further output
        """
        assert self.field_info.annotation is not None
        _help = super().help()
        if is_union(self.field_info.annotation):
            _type = one_from_union(get_args(self.field_info.annotation))

            _help["type"] = _allowed_values(_type)
        else:
            _help["type"] = _allowed_values(self.field_info.annotation)
        _help["default"] = f"default = {self.field_info.default}"
        return _help


class Collection:
    """A collection arguments.

    Annotated as a list or set and its argument can be provided multiple times.
    For example : `my_cli --items item1 --items item2`
    will be parsed a models with an items collection containing item1 and item2

    """

    def __init__(self, field: str, field_info: FieldInfo):
        """Init.

        Args:
            field: field name as defined in the class (a class attribute)
            field_info: Pydantic fieldinfo
        """
        self.field = field
        self.field_info = field_info
        # In case of an error we want to know which keyword was used (like --proceed or -p etc.)
        # We store what used argument here.
        self.used_arg: str = ""
        self.required: bool = True
        self._match: dict[str, list] = {}

    @cached_property
    def short_keys(self) -> list[str]:
        return [
            _to_short(short.short)
            for short in self.field_info.metadata
            if isinstance(short, Short)
        ]

    @cached_property
    def keys(self) -> list[str]:
        return [_to_key(self.field)]

    @cached_property
    def user_keys(self) -> list[str]:
        """Argument keys (like --verbose or --value) provided by a user to indicate a keyword or flag.

        Many times this is a list of normalized pydantic fields or provided shorthand names.
        """
        return self.keys + self.short_keys

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        try:
            if values[idx] not in self.user_keys:
                return False, idx
        except IndexError:
            return False, idx
        self.used_arg = values[idx]

        matches = self._match.setdefault(self.field, [])
        matches.append(values[idx + 1])

        return True, idx + 2

    def parse(self) -> dict[str, list]:
        return self._match

    def help(self) -> THelp:
        """Help data based on field information.

        Returns:
            Help information. To be processed for further output
        """
        desc = (self.field_info.description or "") + " Can be applied multiple times."
        return {
            "arguments": (f'{"/".join(self.short_keys)} {"/".join(self.keys)}').strip(),
            "description": desc,
            "type": str(self.field_info.annotation),
            "default": "",
        }


class OptionalCollection(Collection):
    def __init__(self, field: str, field_info: FieldInfo):
        super().__init__(field, field_info)
        self.required = False

    def help(self) -> THelp:
        """Help data based on field information.

        Returns:
            Help information. To be processed for further output
        """
        _help = super().help()
        _help["default"] = f"default = {self.field_info.default}"
        return _help


class Boolean:
    """A positional (required) boolean flag value."""

    def __init__(self, field: str, field_info: FieldInfo):
        """Init.

        Args:
            field: field name as defined in the class (a class attribute)
            field_info: Pydantic fieldinfo
        """
        self.field = field
        self.field_info = field_info
        # In case of an error we want to know which keyword was used (like --proceed or -p etc.)
        # We store that used argument here.
        self.used_arg: str = ""
        self.required: bool = True
        self._match: dict[str, bool] = {}

    @cached_property
    def _short_true_keys(self) -> list[str]:
        """Return a list of 'shorts' to a list of short hand arguments.

        Example:
            ['a','b'] --> ['-a','-b']
        """
        return [_to_short(short.short) for short in self.field_info.metadata]

    @cached_property
    def _short_false_keys(self) -> list[str]:
        """Return a list of 'shorts' to a list of negated short hand arguments.

        Example:
            ['a','b'] --> ['--no-a','no-b']
        """
        return [_to_false_short(short.short) for short in self.field_info.metadata]

    @cached_property
    def _true_keys(self) -> list[str]:
        """Return a list of argument keys."""
        return [_to_key(self.field)]

    @cached_property
    def _false_keys(self) -> list[str]:
        """Return a list of negated argument keys."""
        return [_to_false_key(self.field)]

    @cached_property
    def short_keys(self) -> list[str]:
        return self._short_true_keys + self._short_false_keys

    @cached_property
    def keys(self) -> list[str]:
        return self._true_keys + self._false_keys

    @cached_property
    def user_keys(self) -> list[str]:
        """Argument keys (like --verbose or --value) provided by a user to indicate a keyword or flag.

        Many times this is a list of normalized pydantic fields or provided shorthand names.
        """
        return self.short_keys + self.keys

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        if len(values) <= idx:
            return False, idx

        if values[idx] in self.user_keys:
            self.used_arg = values[idx]
            self._match[self.field] = (
                values[idx] in self._true_keys + self._short_true_keys
            )
            return True, idx + 1
        return False, idx

    def parse(self) -> dict[str, bool]:
        """Return the token data in a parseable way.

        This mean returning a (partial) dict with a key, value pair
        which is to be consumed by pydantic.
        """
        return self._match

    def help(self) -> THelp:
        """Help data based on field information.

        Returns:
            Help information. To be processed for further output
        """
        return {
            "arguments": (f'{"/".join(self.short_keys)} {"/".join(self.keys)}').strip(),
            "description": self.field_info.description or "",
            "type": "bool",
            "default": "",
        }


class OptionalBoolean(Boolean):
    def __init__(self, field: str, field_info: FieldInfo):
        super().__init__(field, field_info)
        self.required: bool = False

    @cached_property
    def short_keys(self) -> list[str]:
        if self.field_info.default is False:
            return self._short_true_keys
        return self._short_false_keys

    @cached_property
    def keys(self) -> list[str]:
        if self.field_info.default is False:
            return self._true_keys
        return self._false_keys

    @cached_property
    def user_keys(self) -> list[str]:
        """Argument keys (like --verbose or --value) provided by a user to indicate a keyword or flag.

        Many times this is a list of normalized pydantic fields or provided shorthand names.
        """
        if self.field_info.default is False:
            return self._true_keys + self._short_true_keys
        else:
            return self._false_keys + self._short_false_keys

    def help(self) -> THelp:
        """Help data based on field information.

        Returns:
            Help information. To be processed for further output
        """
        _help = super().help()
        _help["default"] = f"default = {self.field_info.default!r}"
        return _help


class Command(Generic[TPydanticModel]):
    """The main/base class of your CLI.

    There will be only one of this in your CLI.
    """

    def __init__(
        self,
        field: str,
        cls: type[TPydanticModel],
        parent: "Command" | "Subcommand" | None,
    ):
        self.field = field
        self.cls = cls
        self.parent = parent
        self._match: dict[str, str | bool | list | None] = {}

        self.tokens: dict[
            str,
            Positional
            | Boolean
            | OptionalBoolean
            | Optional
            | Collection
            | OptionalCollection,
        ] = {}
        self.sub_commands: list["Subcommand"] = []

    @cached_property
    def user_keys(self) -> list[str]:
        """Return the name of the main command that started this cli tool.

        This name is most of times a full path to the python entrypoint.
        We are only interested in the last item of this call.
        """
        keys = (self.field.split("/")[-1]).split("\\")[-1]
        return [keys]

    def match(self, idx: int, arguments: list[str]) -> tuple[bool, int]:
        """Check for token match.

        As a result the subcommand has been stripped down to a one-branch tree, meaning
        all sub_commands collections in all (nested)
        subcommands have only one or no children.


        Args:
            idx: arguments index to start the matching from.
            arguments: the list of provided arguments that need parsing

        Returns:
            tuple of bool and int.
                bool indicates whether to continue matching
                int indicates the new starting point for the next token to match.
        """
        start_idx = idx

        values_count = len(arguments)

        def _check_arg_or_optional(_idx: int, values: list[str]) -> tuple[bool, int]:
            """Every arg in the values list must match one of the tokens in the model."""
            if values_count == _idx:
                return False, _idx
            if values[_idx] in _HELP_KEYS:
                _help.help(self)
                sys.exit(0)
            for arg in self.tokens.values():
                success, _idx = arg.match(_idx, values)
                if success:
                    break
            else:
                return False, _idx
            return True, _idx

        found_match = True
        while found_match:
            found_match, idx = _check_arg_or_optional(idx, arguments)

        # no more match is found. Now we need to check whether all postional (required) arguments
        # have been matched. If not, we have no match for this command.
        non_matching_required_tokens = [
            token
            for token in self.tokens.values()
            if token.required and not token._match
        ]
        if non_matching_required_tokens:
            # only erroring on first token for now.
            # todo: fix reporting on multiple missing positional arguments.
            raise _exceptions.MissingPositional(
                "/".join(non_matching_required_tokens[0].user_keys), idx, arguments
            )

        # We now need to check whether this command has any subcommands.
        # If no subcommands are inside this command we have a match.
        if len(self.sub_commands) == 0:
            return True, idx

        # This command has a subcommand.
        # We now try and match each subcommand with the remainder of the provided arguments.

        # We are going to parse all available subcommands. Only one can exist
        subcommand: Subcommand | None = None
        for sub_command in self.sub_commands:
            success, idx = sub_command.match(idx, arguments)
            if success:
                if subcommand:
                    raise ValueError(
                        "more than one solution-tree is found. Don't know what to do now."
                    )
                subcommand = sub_command

        if not subcommand:
            return False, start_idx

        self.sub_commands = [subcommand]

        return True, idx

    def parse(self) -> TPydanticModel:
        """Populate all tokens with the provided arguments."""
        [self._match.update(parsed.parse()) for parsed in self.tokens.values()]

        if self.sub_commands:
            subcommand = self.sub_commands[0]
            self._match[subcommand.field] = subcommand.parse()
        try:
            return self.cls.model_validate(self._match)
        except ValidationError as err:
            raise _exceptions.FieldError(err, token=self)


class Subcommand(Command):
    @cached_property
    def user_keys(self) -> list[str]:
        snaked = to_snake(self.cls.__name__)
        return [snaked.replace("_", "-")]

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        """Check for token match.

        As a result the subcommand has been stripped down to a one-branch tree, meaning
        all sub_commands collections in all (nested)
        subcommands have only one or no children.


        Args:
            idx: values index to start the matching from.
            values: the list of provided arguments that need parsing

        Returns:
            tuple of bool and int.
                bool indicates whether to continue matching
                int indicates the new starting point for the next token to match.
        """
        try:
            if values[idx] not in self.user_keys:
                return False, idx
        except IndexError:
            return False, idx

        return super().match(idx + 1, values)

    def help(self) -> THelp:
        """Help data based on field information.

        Returns:
            Help information. To be processed for further output
        """
        return {
            "arguments": f'{"/".join(self.user_keys)}',
            "description": self.cls.__doc__ or "",
            "type": "",
            "default": "",
        }
