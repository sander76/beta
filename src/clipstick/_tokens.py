from __future__ import annotations

import sys
from functools import cached_property
from typing import Final, Generic, TypeVar, get_args

from pydantic import BaseModel, ValidationError
from pydantic.alias_generators import to_snake
from pydantic.fields import FieldInfo
from rich.text import Text

from clipstick import _exceptions, _help
from clipstick._annotations import Short
from clipstick._style import ARGUMENTS_STYLE

TPydanticModel = TypeVar("TPydanticModel", bound=BaseModel)


def _to_false_key(field: str) -> str:
    return f"--no-{field.replace('_','-')}"


def _to_key(field: str) -> str:
    return f"--{field.replace('_','-')}"


def _to_short(field: str) -> str:
    return f"-{field}"


def _to_false_short(field: str) -> str:
    return f"-no-{field}"


class PositionalArg:
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

    @cached_property
    def help_arguments(self) -> Text:
        return Text("/".join(self.user_keys), style=ARGUMENTS_STYLE)

    @cached_property
    def help_text(self) -> str:
        return self.field_info.description or ""

    @cached_property
    def help_type(self) -> Text | str:
        if self.field_info.annotation:
            return Text(f"[{self.field_info.annotation.__name__}]")
        return "[]"

    @cached_property
    def help_default(self) -> str | Text:
        return ""


class Choice(PositionalArg):
    @cached_property
    def help_type(self) -> Text:
        options = get_args(self.field_info.annotation)
        return Text(f"[allowed values: {', '.join(options)}]")


class OptionalKeyArgs:
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

    @cached_property
    def help_arguments(self) -> Text:
        return Text(
            (
                f'{"/".join(self.short_keys)} {"/".join(self.keys)}'
            ).strip(),  # doing a strip to remove leading space when short_keys is empty.
            style=ARGUMENTS_STYLE,
        )

    @cached_property
    def help_text(self) -> str:
        return self.field_info.description or ""

    @cached_property
    def help_type(self) -> Text | str:
        if self.field_info.annotation:
            return Text(f"[{self.field_info.annotation.__name__}]")
        return "[]"

    @cached_property
    def help_default(self) -> Text:
        return Text(f"[default = {self.field_info.default}]")


class OptionalChoice(OptionalKeyArgs):
    @cached_property
    def help_type(self) -> Text:
        options = get_args(self.field_info.annotation)
        return Text(f"[allowed values: {', '.join(options)}]")


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

    @cached_property
    def help_arguments(self) -> Text:
        return Text(
            (f'{"/".join(self.short_keys)} {"/".join(self.keys)}').strip(),
            style=ARGUMENTS_STYLE,
        )

    @cached_property
    def help_text(self) -> str:
        extra = " Can be applied multiple times."
        if self.field_info.description:
            return self.field_info.description + extra
        return extra

    @cached_property
    def help_type(self) -> Text:
        return Text(f"[{self.field_info.annotation or 'list'}]")

    @cached_property
    def help_default(self) -> str | Text:
        return Text(f"[default = {self.field_info.default}]")


class OptionalCollection(Collection):
    def __init__(self, field: str, field_info: FieldInfo):
        super().__init__(field, field_info)
        self.required = False

    @cached_property
    def help_default(self) -> Text:
        return Text(f"[default = {self.field_info.default}]")


class BooleanFlag:
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
        # We store what used argument here.
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
        return self._short_false_keys + self._short_true_keys

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

    @cached_property
    def help_arguments(self) -> Text:
        return Text(
            (f'{"/".join(self.short_keys)} {"/".join(self.keys)}').strip(),
            style=ARGUMENTS_STYLE,
        )

    @cached_property
    def help_text(self) -> str:
        return self.field_info.description or ""

    @cached_property
    def help_type(self) -> Text:
        return Text("[bool]")

    @cached_property
    def help_default(self) -> str | Text:
        return Text(f"[default = {self.field_info.default}]")


class OptionalBooleanFlag(BooleanFlag):
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

    @cached_property
    def help_default(self) -> str | Text:
        return Text(f"[default = {self.field_info.default}]")


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
            PositionalArg
            | BooleanFlag
            | OptionalBooleanFlag
            | OptionalKeyArgs
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

        if _is_help_key(idx, arguments):
            _help.help(self)
            sys.exit(0)

        values_count = len(arguments)

        def _check_arg_or_optional(_idx: int, values: list[str]) -> tuple[bool, int]:
            """Every arg in the values list must match one of the tokens in the model."""
            if values_count == _idx:
                return False, _idx
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

    @cached_property
    def help_arguments(self) -> Text:
        return Text(f'{"/".join(self.user_keys)}', style=ARGUMENTS_STYLE)


def _is_help_key(idx, values: list[str]) -> bool:
    try:
        if values[idx] == "-h":
            return True
    except IndexError:
        return False
    return False
