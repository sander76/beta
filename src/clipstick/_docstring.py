import ast
import inspect
import textwrap

from pydantic import BaseModel


def set_undefined_field_descriptions_from_var_docstrings(
    model: type[BaseModel],
) -> dict[str, str]:
    docs: dict[str, str] = {}
    module = ast.parse(textwrap.dedent(inspect.getsource(model)))
    assert isinstance(module, ast.Module)
    class_def = module.body[0]
    assert isinstance(class_def, ast.ClassDef)
    if len(class_def.body) < 2:
        return docs

    for last, node in zip(class_def.body, class_def.body[1:]):
        if not (
            isinstance(last, ast.AnnAssign)
            and isinstance(last.target, ast.Name)
            and isinstance(node, ast.Expr)
        ):
            continue

        doc_node = node.value
        if isinstance(doc_node, ast.Constant):
            docstring = doc_node.value  # 'regular' variable doc string
        else:
            raise NotImplementedError(doc_node)  # pragma: nocover
        docs[last.target.id] = docstring

    return docs


def docstring_from_pydantic_model(model: type[BaseModel]) -> None:
    docs = set_undefined_field_descriptions_from_var_docstrings(model)

    for prop, field_info in model.model_fields.items():
        if field_info.description is not None:
            # has precedence.
            continue
        field_info.description = docs.get(prop, "")


def docstring_from_dataclass(model) -> None:
    docs = set_undefined_field_descriptions_from_var_docstrings(model)
    model.__clipstick_docstring = {}
    for prop, annotation in model.__annotations__.items():
        model.__clipstick_docstring[prop] = docs.get(prop, None)
