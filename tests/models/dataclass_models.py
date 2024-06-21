from dataclasses import dataclass, field
from typing import Annotated, Literal, Optional, Union

from clipstick._annotations import short


@dataclass
class SimpleModel:
    my_value: str


@dataclass
class IntModel:
    my_value: int


@dataclass
class StrModelDefault:
    my_value: str = "ABC"


@dataclass
class Info:
    """Show information about this repo"""

    verbose: bool = True


@dataclass
class Clone:
    """Clone a repo."""

    depth: int


@dataclass
class Remote:
    """Clone a git repository."""

    sub_command: Clone | Info

    url: str = "https://mysuperrepo"
    """Url of the git repo."""


@dataclass
class Merge:
    """Git merge command."""

    branch: str
    """Git branch to merge into current branch."""


@dataclass
class MyGitModel:
    """My custom git cli."""

    sub_command: Remote | Merge


@dataclass
class FlagDefaultFalse:
    """A model with flag."""

    proceed: bool = False
    """continue with this operation."""


@dataclass
class ModelWithChoice:
    choice: Literal["option1", "option2"]


@dataclass
class ModelWithOptionalChoice:
    choice: Literal["option1", "option2"] = "option1"
    """A choice with a default."""


@dataclass
class ModelWithOptionalIntChoice:
    choice: Literal[1, 2] = 1
    """A choice with a default."""


@dataclass
class ModelWithOptionalNoneChoice:
    choice: Literal["option1", "option2"] | None = None
    """A choice with a default."""


@dataclass
class OptionalsModel:
    """A model with only optionals."""

    value_1: int = 10
    """Optional value 1."""

    value_2: str = "ABC"


@dataclass
class OptionalWithShort:
    value_1: Annotated[int, short("v")] = 10


@dataclass
class OptionalValueNoneOptional:
    value_1: Optional[int] = None


@dataclass
class OptionalValueNoneUnion:
    value_1: Union[int, None] = None


@dataclass
class OptionalValueNonePipe:
    value_1: int | None = None


@dataclass
class CollectionModel:
    my_list: Annotated[list[int], short("m")] = field(default_factory=lambda: [9])
