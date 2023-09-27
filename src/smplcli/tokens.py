from dataclasses import dataclass, field
import sys

from types import UnionType
from typing import Any, ForwardRef, Protocol, TypeAlias, Union, get_args
from pydantic.fields import FieldInfo

from pydantic import BaseModel

from smplcli.docstring import set_undefined_field_descriptions_from_var_docstrings


@dataclass
class Token:
    key: str

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        """Consume a list of values and return the new index for
        a next token to start consuming."""
        raise NotImplementedError()

    def parse(self, values: list[str]) -> dict[str, str]:
        raise NotImplementedError()


@dataclass
class PositionalArg(Token):
    key: str
    indices: slice | None = None

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        try:
            if values[idx].startswith("--"):
                # Not a positional. No match.
                return False, idx
        except IndexError:
            return False, idx
        # would fit as a positional
        self.indices = slice(idx, idx + 1)
        return True, idx + 1

    def parse(self, values: list[str]) -> dict[str, str]:
        return {self.key: values[self.indices][0]}


@dataclass
class OptionalArg(Token):
    key: str
    indices: slice | None = None

    def match(self, idx: int, values: list[str]) -> tuple[bool, int]:
        try:
            if not values[idx] == f"--{self.key}":
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
class Subcommand(Token):
    key: str
    sub_command_name: str
    cls: type[BaseModel]
    indices: slice | None = None

    args: list[Token] = field(default_factory=list)
    sub_commands: list["Subcommand"] = field(default_factory=list)

    def tokens(self) -> list[list["Subcommand"]]:
        base = [self]

        if self.sub_commands:
            args = []
            for sub in self.sub_commands:
                for token in sub.tokens():
                    new_ = base + token
                    args.append(new_)
            return args
        return [base]

    def help(self):
        print(self.cls.__doc__)
        print("")
        for arg in self.args:
            try:
                field_info = self.cls.model_fields[arg.key]
                print(field_info.description)
            except KeyError:
                # a key error might be raised when -for example- we're trying
                # to get the field info of a -h / --help argument. which doesn't exist.
                pass
        for sub_command in self.sub_commands:
            print(sub_command.cls.__name__, "\n\n")

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
            if not values[idx] == self.sub_command_name:
                return False, start_idx
        except IndexError:
            return False, start_idx

        self.indices = slice(idx, idx + 1)

        idx += 1
        for arg in self.args:
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

        self.sub_commands = [succesfull_subcommands[0][2]]
        return True, idx + succesfull_subcommands[0][1]

    def parse(self, arguments: list[str]) -> dict[str, BaseModel]:
        """Populate all tokens with the provided arguments."""
        args: dict[str, str] = {}
        [args.update(parsed.parse(arguments)) for parsed in self.args]
        sub_commands: dict[str, BaseModel] = {}
        assert len(self.sub_commands) <= 1
        [sub_commands.update(parsed.parse(arguments)) for parsed in self.sub_commands]

        model = self.cls(**args, **sub_commands)

        return {self.key: model}


@dataclass
class HelpArg(Token):
    key: str
    sub_command: Subcommand
    indices: slice | None = None

    def match(self, idx, values: list[str]) -> tuple[bool, int]:
        try:
            if not values[idx] == "-h":
                return True, idx
        except IndexError:
            return True, idx
        self.indices = slice(idx, len(values))
        return True, idx + len(values)

    def parse(self, values: list[str]) -> dict[str, str]:
        if self.indices:
            self.sub_command.help()
            sys.exit(0)
        return {}


def _is_subcommand(attribute: str, field_info: FieldInfo) -> bool:
    if not isinstance(field_info.annotation, UnionType):
        return False
    args = get_args(field_info.annotation)
    if not all(issubclass(arg, BaseModel) for arg in args):
        return False
    if not field_info.is_required():
        raise ValueError("Should be required values.")
    return True


def tokenize(model: type[BaseModel], sub_command: Subcommand) -> None:
    # todo: move this somewhere else.
    set_undefined_field_descriptions_from_var_docstrings(model)

    sub_command.args.append(HelpArg("help", sub_command))
    for key, value in model.model_fields.items():
        if _is_subcommand(key, value):
            for annotated_model in get_args(value.annotation):
                new_sub_command = Subcommand(
                    key, annotated_model.__name__, cls=annotated_model
                )

                sub_command.sub_commands.append(new_sub_command)
                tokenize(annotated_model, new_sub_command)

        elif value.is_required():
            # becomes a positional
            sub_command.args.append(PositionalArg(key))
        else:
            sub_command.args.append(OptionalArg(key))


def parse(model: type[BaseModel], args: list[str]) -> BaseModel:
    args = ["__main_entry__"] + args
    root_node = Subcommand("__main_entry__", "__main_entry__", model)
    tokenize(model=model, sub_command=root_node)

    root_node.match(0, args)
    parsed = root_node.parse(args)
    return parsed["__main_entry__"]
