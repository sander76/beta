from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError
from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from clipstick import _tokens
from clipstick._style import ARGUMENTS_STYLE

if TYPE_CHECKING:
    from clipstick.__intermediary import Arg


class ClipStickError(Exception):
    """Base clipstick Exception."""

    def __init__(self, *message: str | Text) -> None:
        super().__init__()
        self.message: tuple[str | Text, ...] = message

    def __rich_console__(self, _: Console, __: ConsoleOptions) -> RenderResult:
        for line in self.message:
            yield line

    def __str__(self) -> str:
        return str(self.message)


class MissingPositional(ClipStickError):
    """Raised when an incorrect number of positionals is provided."""

    def __init__(self, key: str, idx: int, values: list[str]) -> None:
        super().__init__(
            Text.assemble(
                "Missing a value for positional argument ",
                Text(f"{key!r}", style=ARGUMENTS_STYLE),
            )
        )


class InvalidModel(ClipStickError):
    """Raised when your clipstick model is invalid."""


class InvalidTypesInUnion(InvalidModel):
    def __init__(self) -> None:
        super().__init__("A union composing a subcommand must all be of type BaseModel")


class NoDefaultAllowedForSubcommand(InvalidModel):
    def __init__(self) -> None:
        super().__init__("A subcommand cannot have a default value.")


class TooManySubcommands(InvalidModel):
    def __init__(self) -> None:
        super().__init__("Only one subcommand per model allowed.")


class InvalidUnion(InvalidModel):
    def __init__(self, *message: str | Text) -> None:
        super().__init__(
            "A union type can only contain 2 types of which one must be None (the default)"
        )


class OnlyOneTypeAllowedInCollection(InvalidModel):
    def __init__(self, arg: Arg) -> _tokens.NoneType:
        super().__init__(
            f"A collection can only contain one type. {arg.key=}, {arg.type}"
        )


class TooManyShortsException(ClipStickError):
    def __init__(self, model, shorts: list[str]) -> None:
        super().__init__("too many shorts defined inside model")
        self._model = model
        self._shorts = shorts

    def __str__(self):
        return f"{self.message}, model={self._model}, shorts={self._shorts}"


class FieldError(ClipStickError):
    """A pydantic validation error wrapper."""

    def __init__(
        self,
        exception: ValidationError,
        token: _tokens.Command | _tokens.Subcommand,
    ) -> None:
        errors: list[str | Text] = []
        for error in exception.errors():
            input = error["input"]
            error_msg = error["msg"]
            # todo: most of times I need just the fist item.
            # Have not encountered a situation where I need something else,
            # but it will need some investigating though.
            failing_field = error["loc"][0]
            assert isinstance(failing_field, str)
            # find the token by using the input value (which is the key) that is causing the exception.
            error_text = Text("Incorrect value for ")

            failing_token = token.tokens[failing_field]

            error_text.append(Text(failing_token.used_arg, style=ARGUMENTS_STYLE))

            # this token relates to a positional argument.
            if isinstance(token, _tokens.Subcommand):
                error_text.append(f" in {token.user_keys[0]} ")

            error_text.append(f" ({input!r}). {error_msg}")
            errors.append(error_text)

        super().__init__(*errors)
