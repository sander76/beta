from inspect import isclass
from itertools import chain
from typing import Iterator, Literal, get_args

from pydantic import BaseModel

from clipstick._annotations import Short
from clipstick._docstring import set_undefined_field_descriptions_from_var_docstrings
from clipstick._exceptions import (
    InvalidTypesInUnion,
    NoDefaultAllowedForSubcommand,
    TooManyShortsException,
    TooManySubcommands,
)
from clipstick._tokens import (
    is_union,
    one_from_union,
)


def _is_subcommand(annotation: type) -> bool:
    """Check if the field annotated as a subcommand."""
    args = get_args(annotation)
    if not all((isclass(arg) for arg in args)):
        return False
    if not any(issubclass(arg, BaseModel) for arg in args):
        return False

    if not all(issubclass(arg, BaseModel) for arg in args):
        raise InvalidTypesInUnion()
    return True


def _is_boolean_type(annotation: type) -> bool:
    if annotation is bool:
        return True
    return False


def _is_collection_type(annotation: type) -> bool:
    if getattr(annotation, "__origin__", None) in (list, set):
        return True
    return False


def _check_origin_type(annotation: object, _type: object) -> bool:
    origin = getattr(annotation, "__origin__", None)
    if origin is _type:
        return True
    return False


def _is_choice(annotation: type) -> bool:
    return _check_origin_type(annotation, Literal)


def validate_model(model: type[BaseModel]) -> None:
    """Validate the input model to see it is useful for cli generation.

    Done before anything else.
    """
    # todo: validate only one subcommand.

    # todo: a subcommand must always be the last one defined.

    # todo: validate no pydantic model as field value.

    # check shorthands per model to be unique.
    _validate_shorts(model)


def _validate_shorts(model: type[BaseModel]) -> None:
    """Iterate over the complete cli model and validate each model of short-hand uniqueness.

    Returns:
        None if all ok

    Raises:
        ValueError when validation has failed.
    """
    for model in iter_over_model(model):
        _validate_shorts_in_model(model)


def _validate_shorts_in_model(model: type[BaseModel]):
    shorts = [
        short.short
        for short in chain(*(field.metadata for field in model.model_fields.values()))
        if isinstance(short, Short)
    ]

    unique_shorts = set(shorts)

    if len(shorts) == len(unique_shorts):
        return
    raise TooManyShortsException(model, shorts)


def iter_over_model(model: type[BaseModel]) -> Iterator[type[BaseModel]]:
    """Return all BaseModels within a provided BaseModel."""
    try:
        if issubclass(model, BaseModel):
            yield model
    except TypeError:
        # python version 3.10 cannot handle annotated types.
        # as soon as we drop support for 3.10 this call can be rewritten.
        pass

    if fields := getattr(model, "model_fields", None):
        for item in fields.values():
            yield from iter_over_model(item.annotation)
            for arg in get_args(item.annotation):
                yield from iter_over_model(arg)
