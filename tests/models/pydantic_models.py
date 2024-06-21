from typing import Annotated, Literal, Optional, Union

from clipstick._annotations import short
from pydantic import BaseModel


class SimpleModel(BaseModel):
    my_value: str


class StrModelDefault(BaseModel):
    my_value: str = "ABC"


class IntModel(BaseModel):
    my_value: int


class Info(BaseModel):
    verbose: bool = True


class Clone(BaseModel):
    depth: int


class Remote(BaseModel):
    url: str = "https://mysuperrepo"

    sub_command: Clone | Info


class Merge(BaseModel):
    branch: str


class MyGitModel(BaseModel):
    sub_command: Remote | Merge


class FlagDefaultFalse(BaseModel):
    proceed: bool = False


class ModelWithChoice(BaseModel):
    choice: Literal["option1", "option2"]


class ModelWithOptionalChoice(BaseModel):
    choice: Literal["option1", "option2"] = "option1"


class ModelWithOptionalIntChoice(BaseModel):
    choice: Literal[1, 2] = 1


class ModelWithOptionalNoneChoice(BaseModel):
    choice: Literal["option1", "option2"] | None = None


class OptionalsModel(BaseModel):
    value_1: int = 10

    value_2: str = "ABC"


class OptionalWithShort(BaseModel):
    value_1: Annotated[int, short("v")] = 10


class OptionalValueNoneOptional(BaseModel):
    value_1: Optional[int] = None


class OptionalValueNoneUnion(BaseModel):
    value_1: Union[int, None] = None


class OptionalValueNonePipe(BaseModel):
    value_1: int | None = None


class CollectionModel(BaseModel):
    my_list: Annotated[list[int], short("m")] = [9]
    """A list type object"""
