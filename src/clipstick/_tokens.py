from __future__ import annotations
from dataclasses import dataclass, field
from functools import cached_property
import sys

from typing import Generic, TypeVar
from itertools import chain
from pydantic import BaseModel
from pydantic.alias_generators import to_snake
from pydantic.fields import FieldInfo
from clipstick import _help

TTokenType = TypeVar("TTokenType")
TPydanticModel = TypeVar("TPydanticModel", bound=BaseModel)


@dataclass
class Token(Generic[TTokenType]):
    """Represents either a pydantic model or a pydantic field.

    It serves two (many ?) purposes:

    - Evaluating and parsing the provided arguments (the cli entries)
    - Generating help information based on pydantic data.
    """

    key: str

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        """Try to match a (range of) value(s) starting from an index.

        Matching logic is implemented depending on argument type (like positional, optional etc.)

        If a match is found it will be added to the list of tokens which are used for final parsing.
        """
        raise NotImplementedError()

    def parse(self, values: list[str]) -> dict[str, TTokenType]:
        """Parse data from the provided values based on the match logic implemented in this class."""
        raise NotImplementedError()

    @property
    def user_key(self) -> list[str]:
        raise NotImplementedError()


@dataclass
class PositionalArg(Token[str]):
    key: str
    field_info: FieldInfo
    indices: slice | None = None

    @property
    def user_key(self) -> list[str]:
        return [self.key.replace("_", "-")]

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        try:
            if values[idx].startswith("-"):
                # Not a positional. No match.
                return False, idx
        except IndexError:
            return False, idx
        # would fit as a positional
        self.indices = slice(idx, idx + 1)
        return True, idx + 1

    def parse(self, values: list[str]) -> dict[str, str]:
        if self.indices:
            return {self.key: values[self.indices][0]}
        raise ValueError("Expecting a slice object. Got None.")


@dataclass
class OptionalKeyArgs(Token[str]):
    key: str
    field_info: FieldInfo
    indices: slice | None = None

    @cached_property
    def short_keys(self) -> list[str]:
        return [short.short for short in self.field_info.metadata]

    @property
    def user_key(self) -> list[str]:
        return [f"--{self.key.replace('_','-')}"] + [
            f"-{short}" for short in self.short_keys
        ]

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        try:
            if values[idx] not in self.user_key:
                # As this is an optional, we are returning true to continue matching.
                return True, idx
        except IndexError:
            # As this is an optional, we are returning true to continue matching.
            return True, idx

        # consume next two values
        self.indices = slice(idx, idx + 2)
        return True, idx + 2

    def parse(self, values: list[str]) -> dict[str, str]:
        if self.indices:
            return {self.key: values[self.indices][-1]}
        return {}


@dataclass
class BooleanFlag(Token[bool]):
    """A positional (required) boolean flag value."""

    key: str
    """A pydantic field key/name"""
    field_info: FieldInfo
    indices: slice | None = None

    @cached_property
    def arg_key(self) -> str:
        return self.key.replace("_", "-")

    @cached_property
    def short_keys(self) -> list[str]:
        return [short.short for short in self.field_info.metadata]

    @property
    def true_values(self) -> list[str]:
        return [f"--{self.arg_key}"] + [f"-{short}" for short in self.short_keys]

    @property
    def false_values(self) -> list[str]:
        return [f"--no-{self.arg_key}"] + [f"-no-{short}" for short in self.short_keys]

    @property
    def user_key(self) -> list[str]:
        return self.true_values + self.false_values

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        if len(values) <= idx:
            return False, idx

        if values[idx] in self.user_key:
            self.indices = slice(idx, idx + 1)
            return True, idx + 1
        return False, idx

    def parse(self, values: list[str]) -> dict[str, bool]:
        if self.indices:
            val = values[self.indices][0] in self.true_values
            return {self.key: val}
        return {}


@dataclass
class OptionalBooleanFlag(BooleanFlag):
    key: str
    field_info: FieldInfo
    indices: slice | None = None

    @cached_property
    def user_key(self) -> list[str]:
        if self.field_info.default is False:
            return self.true_values
        else:
            return self.false_values

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        if len(values) <= idx:
            return True, idx

        if values[idx] in self.user_key:
            self.indices = slice(idx, idx + 1)
            return True, idx + 1
        return True, idx


@dataclass
class Command(Token[TPydanticModel]):
    key: str
    """Reference to the key in the pydantic model."""

    cls: type[TPydanticModel]
    """Pydantic class. Used for instantiating this command."""

    parent: "Command" | "Subcommand" | None
    """The full command that got you here."""

    indices: slice | None = None
    """The indices which are consumed of the provided arguments."""

    args: list[PositionalArg | BooleanFlag] = field(default_factory=list)
    """Collection of required arguments associated with this command."""

    optional_kwargs: list[OptionalKeyArgs | OptionalBooleanFlag] = field(
        default_factory=list
    )
    """Collection of optional keyword arguments associated with this command."""

    sub_commands: list["Subcommand"] = field(default_factory=list)

    @property
    def user_key(self) -> list[str]:
        return [self.key]

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
        start_idx = idx

        if _is_help_key(idx, values):
            _help.help(self)
            sys.exit(0)
        for arg in chain(self.args, self.optional_kwargs):
            success, idx = arg.match(idx, values)
            if not success:
                return False, start_idx

        if len(self.sub_commands) == 0:
            return True, idx

        subcommands: list[tuple[bool, int, Subcommand]] = []
        for sub_command in self.sub_commands:
            sub_command_start_idx = idx
            result = sub_command.match(sub_command_start_idx, values)
            subcommands.append((*result, sub_command))

        succesfull_subcommands = [
            sub_command_structure
            for sub_command_structure in subcommands
            if sub_command_structure[0] is True
        ]

        if len(succesfull_subcommands) > 1:
            raise ValueError(
                "more than one solution-tree is found. Don't know what to do now."
            )
        if len(succesfull_subcommands) == 0:
            return False, start_idx
        _, new_idx, sub_commands = succesfull_subcommands[0]
        self.sub_commands = [sub_commands]

        # self.sub_commands = [succesfull_subcommands[0][2]]
        return True, new_idx

    def parse(self, arguments: list[str]) -> dict[str, TPydanticModel]:
        """Populate all tokens with the provided arguments."""
        args: dict[str, str | bool] = {}
        [
            args.update(parsed.parse(arguments))
            for parsed in chain(self.args, self.optional_kwargs)
        ]
        sub_commands: dict[str, BaseModel] = {}
        assert len(self.sub_commands) <= 1
        [sub_commands.update(parsed.parse(arguments)) for parsed in self.sub_commands]

        model = self.cls(**args, **sub_commands)

        return {self.key: model}


@dataclass
class Subcommand(Command):
    @property
    def user_key(self) -> list[str]:
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
        start_idx = idx
        try:
            if values[idx] not in self.user_key:
                return False, start_idx
        except IndexError:
            return False, start_idx

        self.indices = slice(idx, idx + 1)

        idx += 1

        return super().match(idx, values)


def _is_help_key(idx, values: list[str]) -> bool:
    try:
        if values[idx] == "-h":
            return True
    except IndexError:
        return False
    return False
