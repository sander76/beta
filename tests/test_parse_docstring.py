from dataclasses import dataclass
from typing import Annotated

import pytest
from clipstick import _docstring
from clipstick._docstring import set_undefined_field_descriptions_from_var_docstrings
from pydantic import BaseModel, Field


@dataclass
class NestedDataclass:
    a_prop: int
    """some property."""


class GlobalModel(BaseModel):
    my_value_docstring: str
    """Docstring for my_value."""

    my_value_annotation: str = Field(description="Description for my_value.")


class SomeClass:
    class ModelInClass(BaseModel):
        my_value_docstring: str
        """Docstring for my_value."""

        my_value_annotation: str = Field(description="Description for my_value.")


def some_function():
    class ModelInFunction(BaseModel):
        my_value_docstring: str
        """Docstring for my_value."""

        my_value_annotation: str = Field(description="Description for my_value.")

    return ModelInFunction


@pytest.mark.parametrize(
    "model", [GlobalModel, SomeClass.ModelInClass, some_function()]
)
def test_docstring_for_pydantic(model: type[BaseModel]):
    _docstring.docstring_from_pydantic_model(model)
    assert (
        model.model_fields["my_value_docstring"].description
        == "Docstring for my_value."
    )
    assert (
        model.model_fields["my_value_annotation"].description
        == "Description for my_value."
    )


def test_docstring_for_dataclass():
    _docstring.docstring_from_dataclass(NestedDataclass)

    assert NestedDataclass.__clipstick_docstring["a_prop"] == "some property."
