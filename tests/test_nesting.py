import pytest
from clipstick import parse

from tests.models import dataclass_models, pydantic_models


def test_nested_model_nest_1(models):
    result = parse(models.MyGitModel, ["merge", "main"])
    assert result == models.MyGitModel(sub_command=models.Merge(branch="main"))


def test_deeply_nested_default(models):
    result = parse(models.MyGitModel, ["remote", "info"])
    assert result == models.MyGitModel(
        sub_command=models.Remote(sub_command=models.Info(verbose=True))
    )


def test_deeply_nested_model_nest_1(models):
    result = parse(models.MyGitModel, ["remote", "info", "--no-verbose"])
    assert result == models.MyGitModel(
        sub_command=models.Remote(sub_command=models.Info(verbose=False))
    )


def test_deeply_nested_model_nest_2(models):
    result = parse(models.MyGitModel, ["remote", "clone", "11"])
    assert result == models.MyGitModel(
        sub_command=models.Remote(sub_command=models.Clone(depth=11))
    )


def test_deeply_nested_model_nest_3(models):
    model = parse(models.MyGitModel, ["merge", "my_working_branch"])
    assert model == models.MyGitModel(
        sub_command=models.Merge(branch="my_working_branch")
    )
